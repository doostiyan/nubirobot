import sys
import time
import traceback
from abc import ABC
from collections import defaultdict
from decimal import Decimal
from json import JSONDecodeError

from django.conf import settings
from django.core.cache import cache
from requests.exceptions import ReadTimeout

from exchange.blockchain.metrics import metric_set

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
from typing import Any, Dict, Optional

from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin
from exchange.blockchain.validators import validate_near_address


class NearGeneralAPI(NobitexBlockchainAPI, BlockchainUtilsMixin, ABC):
    PRECISION = 24
    default_pagination_limit = 25
    default_pagination_offset = 0
    default_pagination_page = 1
    symbol = 'NEAR'
    cache_key = 'near'
    currency = Currencies.near
    valid_transfer_types = ['Transfer']
    get_txs_keyword = ''
    min_valid_tx_amount = Decimal('0.05')
    tries = 5  # in case of API connection error
    backoff_delay = 0.5  # second
    max_blocks = 100
    BLOCK_TIME = 1.3

    def get_header(self) -> Optional[Dict[str, Any]]:
        return None

    @classmethod
    def validate_address(cls, address: str) -> bool:
        return validate_near_address(address)

    def get_balance(self, address: str) -> dict:
        # NearBlocksAPI rounds the balance to 6 Decimal places
        self.validate_address(address)
        try:
            response = self.request('get_balance', address=address, headers=self.get_header())
        except ConnectionError as e:
            raise APIError(f'{self.symbol} API: Failed to get Balance, connection error') from e
        if response is None:
            raise APIError(f'{self.symbol} API: Get Balance response is None')
        balance_amount = self.parse_balance(response)
        return {
            self.currency: {
                'symbol': self.symbol,
                'amount': balance_amount,
                'address': address
            }
        }

    def get_block_head(self) -> Any:
        try:
            response = self.request('get_block_head', headers=self.get_header())
        except ConnectionError as e:
            raise APIError(f'{self.symbol} API:Failed to get Block Head, connection error') from e
        if not response:
            raise APIError(f'{self.symbol} API: get_block_head: Response is none')
        return self.parse_block_head(response)

    def get_txs(self, address: str, pagination_offset: int = default_pagination_offset,
                pagination_limit: int = default_pagination_limit,
                pagination_page: int = default_pagination_page,
                tx_direction_filter: str = 'incoming') -> list:
        if tx_direction_filter == 'incoming':
            tx_query_direction = 'receiver'
        elif tx_direction_filter == 'outgoing':
            tx_query_direction = 'sender'
        else:
            raise APIError(f'incorrect arg tx_query_direction = {tx_direction_filter}')
        self.validate_address(address)
        block_head = self.get_block_head()
        try:
            response = self.request('get_transactions',
                                    headers=self.get_header(),
                                    pagination_offset=pagination_offset,
                                    pagination_limit=pagination_limit,
                                    pagination_page=pagination_page,
                                    tx_query_direction=tx_query_direction,
                                    address=address)
        except ConnectionError as e:
            raise APIError(f'{self.symbol} API: Failed to get txs, connection error') from e
        transactions = []
        txs = response.get(self.get_txs_keyword)
        for tx in txs:
            if self.validate_transaction(tx, address):
                parsed_tx = self.parse_tx(tx, address, block_head)
                transactions.append(parsed_tx)
        return transactions

    def get_tx_direction(self, tx: dict, address: str) -> Optional[str]:
        to_address = self.parse_tx_receiver(tx).casefold()
        from_address = self.parse_tx_sender(tx).casefold()
        # check self transaction
        if to_address == from_address:
            return None
        if address.casefold() == to_address:
            return 'incoming'
        if address.casefold() == from_address:
            return 'outgoing'
        return None

    def get_tx_details(self, tx_hash: str) -> dict:
        try:
            response = self.request('get_tx_details', headers=self.get_header(), tx_hash=tx_hash)
        except ConnectionError as e:
            raise APIError(f'{self.symbol} API: Failed to get_tx_details, connection error') from e
        if not response:
            raise APIError(f'{self.symbol}: get_tx_detail Response is none')
        return self.parse_tx_details(response)

    def get_latest_block(self, after_block_number: Optional[int] = None, to_block_number: Optional[int] = None,
                         include_inputs: bool = False, include_info: bool = False) -> tuple:
        """
        calculate unprocessed block-height range and list all addresses in all transaction in all blocks in that range
        """
        max_height, min_height = self.calculate_unprocessed_block_range(after_block_number, to_block_number)

        # input_addresses <~> outgoing_txs, output_addresses <~> incoming_txs
        transactions_addresses = {'input_addresses': set(), 'output_addresses': set()}
        transactions_info = {'outgoing_txs': defaultdict(lambda: defaultdict(list)),
                             'incoming_txs': defaultdict(lambda: defaultdict(list))}

        block_height = self.get_addresses_in_block_range(include_info, include_inputs, max_height, min_height,
                                                         transactions_addresses, transactions_info)

        metric_set(name='latest_block_processed', labels=[self.symbol.lower()], amount=block_height - 1)
        cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}',
                  block_height - 1, 86400)
        return transactions_addresses, transactions_info, block_height - 1

    def calculate_unprocessed_block_range(self, after_block_number: Optional[int],
                                          to_block_number: Optional[int]) -> tuple:
        if not to_block_number:
            latest_block_height_mined = self.get_block_head()
            if not latest_block_height_mined:
                raise APIError(f'{self.symbol}: API Not Return block height')
        else:
            latest_block_height_mined = to_block_number
        if not after_block_number:
            latest_block_height_processed = cache. \
                get(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}')
            if latest_block_height_processed is None:
                latest_block_height_processed = latest_block_height_mined - 5
        else:
            latest_block_height_processed = after_block_number

        if latest_block_height_mined > latest_block_height_processed:
            min_height = latest_block_height_processed + 1
        else:
            min_height = latest_block_height_mined + 1
        max_height = min(latest_block_height_mined + 1, min_height + self.max_blocks)
        return max_height, min_height

    def get_addresses_in_block_range(self, include_info: bool, include_inputs: bool, max_height: int, min_height: int,
                                     transactions_addresses: dict, transactions_info: dict) -> int:
        for block_height in range(min_height, max_height):
            try:
                self.get_block_addresses(block_height, transactions_addresses, transactions_info,
                                         include_info, include_inputs)
            except Exception:  # noqa: PERF203
                traceback.print_exception(*sys.exc_info())
                break
        else:
            block_height = max_height
        return block_height

    def get_block_addresses(self, block_height: int, transactions_addresses: dict, transactions_info: dict,
                            include_info: bool, include_inputs: bool) -> None:
        """
            get all transaction of a block and get addresses in each of them
        """
        transactions = self.get_block_transactions(block_height)
        if transactions is None:
            return
        for tx in transactions:
            self.get_tx_addresses(tx, transactions_addresses, transactions_info, include_info, include_inputs)

    def get_block_transactions(self, block_height: int) -> list:
        response = None
        for i in range(self.tries):
            try:
                response = self.request('get_block_txs', headers=self.get_header(), block_height=block_height)
                if not response:
                    raise APIError(f'{self.symbol} Get block API returns empty response')
                break
            except (ConnectionError, APIError, ReadTimeout):
                if i < self.tries - 1:  # i is zero indexed
                    time.sleep(self.backoff_delay)
                    continue
            except JSONDecodeError:
                return []
        return self.parse_block_transactions(response)

    def get_tx_addresses(self, tx: Any, transactions_addresses: dict, transactions_info: dict, include_info: bool,
                         include_inputs: bool) -> None:
        if not self.validate_transaction(tx):
            return
        tx_data = self.parse_transaction_data(tx)
        if tx_data is None:
            return
        from_address = tx_data.get('from')
        to_address = tx_data.get('to')
        value = tx_data.get('amount')
        currency = tx_data.get('currency')

        if not self.validate_tx_amount(value):
            return

        transactions_addresses['output_addresses'].add(to_address)
        if include_inputs:
            transactions_addresses['input_addresses'].add(from_address)

        if include_info:
            tx_hash = tx.get('hash')
            if include_inputs:
                transactions_info['outgoing_txs'][from_address][currency].append({
                    'tx_hash': tx_hash,
                    'value': value,
                })
            transactions_info['incoming_txs'][to_address][currency].append({
                'tx_hash': tx_hash,
                'value': value,
            })

    def validate_tx_amount(self, value: Any) -> bool:
        return value > self.min_valid_tx_amount

    def parse_balance(self, response: Any) -> dict:  # noqa: ARG002
        return {}

    def parse_block_head(self, response: Any) -> Any:  # noqa: ARG002
        return {}

    def validate_transaction(self, tx: Any, address: Optional[str] = None) -> Any:  # noqa: ARG002
        return

    def parse_tx(self, tx: Any, address: str, block_head: int) -> dict:  # noqa: ARG002
        return {}

    def parse_tx_details(self, response: Any) -> dict:  # noqa: ARG002
        return {}

    def validate_transaction_detail(self, details: Any) -> Any:  # noqa: ARG002
        return

    def parse_block_transactions(self, response: Any) -> list:  # noqa: ARG002
        return []

    def parse_transaction_data(self, tx: Any) -> dict:  # noqa: ARG002
        return {}

    def parse_tx_sender(self, tx: Any) -> str:  # noqa: ARG002
        return ''

    def parse_tx_receiver(self, tx: Any) -> str:  # noqa: ARG002
        return ''
