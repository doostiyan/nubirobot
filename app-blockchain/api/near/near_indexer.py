from decimal import Decimal
from typing import Any, Optional

import pytz
from django.conf import settings
from django.core.cache import cache

from exchange.base.parsers import parse_utc_timestamp_nanosecond
from exchange.blockchain.api.near.near_general import NearGeneralAPI
from exchange.blockchain.utils import APIError, ParseError


class NearIndexerAPI(NearGeneralAPI):
    """
    API Doc: use blockchain.scripts.near_indexer_api. https://www.getpostman.com/collections/bebfe04055fa07271a60
    """
    BLOCK_HEAD_OFFSET = 4  # to be sure head-block transactions have been completely inserted into DB
    max_blocks = 400
    _base_url = 'https://blockapi.nobitex1.ir/nearapi/' if settings.IS_PROD else 'http://127.0.0.1:5000/'
    USE_PROXY = False
    get_txs_keyword = 'txs'
    supported_requests = {
        'get_block_head': 'nearindexer_getblockhead',
        'get_addresses': 'nearindexer_getlatestblock?min_height={min_height}&max_height={max_height}',
        'get_transactions': 'nearindexer_gettxs?account_address={address}&direction={tx_query_direction}',
        'get_tx_details': 'nearindexer_gettxdetail?tx_hash={tx_hash}'
    }

    def get_name(self) -> str:
        return 'indexer_api'

    def parse_block_head(self, response: dict) -> int:
        try:
            return int(response.get('block_height'))
        except AttributeError as e:
            raise APIError(f'{self.symbol} get block head parsing error.') from e

    def get_addresses_in_block_range(self, include_info: bool, include_inputs: bool, max_height: int, min_height: int,
                                     transactions_addresses: dict, transactions_info: dict) -> int:
        try:
            latest_block_height_mined = self.get_block_head() - self.BLOCK_HEAD_OFFSET
            if not latest_block_height_mined:
                raise APIError(f'{self.symbol}: API Not Return block height')
            max_height = min(latest_block_height_mined, max_height)
            if min_height > max_height:
                return cache. \
                    get(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}') + 1
            response = self.request('get_addresses', headers=self.get_header(),
                                    min_height=min_height, max_height=max_height)
        except ConnectionError as e:
            raise APIError(f'{self.symbol} API: Failed to address in block range, connection error') from e
        if response is None:
            raise APIError(f'{self.symbol}: get_addresses_in_block_range Response is none')
        self.parse_addresses_in_block_range(response, include_info, include_inputs,
                                            transactions_addresses, transactions_info)
        return max_height + 1

    def parse_addresses_in_block_range(self, results: Any, include_info: bool, include_inputs: bool,
                                       transactions_addresses: dict, transactions_info: dict) -> None:
        for row in results:
            from_address = row.get('from_address')
            to_address = row.get('to_address')
            value = Decimal(row.get('value'))
            if not self.validate_tx_amount(value):
                continue
            currency = self.currency
            transactions_addresses['output_addresses'].add(to_address)
            if include_inputs:
                transactions_addresses['input_addresses'].add(from_address)

            if include_info:
                tx_hash = row.get('tx_hash')
                if include_inputs:
                    transactions_info['outgoing_txs'][from_address][currency].append({
                        'tx_hash': tx_hash,
                        'value': value,
                    })
                transactions_info['incoming_txs'][to_address][currency].append({
                    'tx_hash': tx_hash,
                    'value': value,
                })

    def validate_transaction(self, tx: dict, address: Optional[str] = None) -> bool:
        # as we validate tx status and type in database just checking tx amount
        if not self.validate_tx_amount(Decimal(tx.get('value'))):
            return False
        direction = self.get_tx_direction(tx, address)
        if not direction:
            return False
        return True

    def parse_tx(self, tx: dict, address: str, block_head: int) -> dict:
        try:
            tx_hash = tx.get('tx_hash')
            from_address = self.parse_tx_sender(tx)
            to_address = self.parse_tx_receiver(tx)
            tx_block_height = tx.get('block_height')
            tx_amount = Decimal(tx.get('value'))
            date = parse_utc_timestamp_nanosecond(tx.get('block_time'))
        except AttributeError as e:
            raise ParseError(f'{self.symbol} parsing error Tx is {tx}.') from e
        direction = self.get_tx_direction(tx, address)
        if direction == 'outgoing':
            tx_amount = -tx_amount
        return {
            self.currency: {
                'address': address,
                'hash': tx_hash,
                'from_address': from_address,
                'to_address': to_address,
                'amount': tx_amount,
                'block': tx_block_height,
                'date': date,
                'confirmations': block_head - tx_block_height,
                'direction': direction,
                'raw': ''
            }
        }

    def parse_tx_receiver(self, tx: dict) -> str:
        return tx.get('receiver')

    def parse_tx_sender(self, tx: dict) -> str:
        return tx.get('sender')

    def parse_tx_details(self, response: dict) -> dict:
        try:
            tx_details = response.get('details')
            if self.validate_transaction_detail(tx_details):
                tx_date = parse_utc_timestamp_nanosecond(tx_details.get('date')).replace(tzinfo=pytz.UTC)
                transfer = [{
                    'type': tx_details.get('type'),
                    'symbol': self.symbol,
                    'currency': self.currency,
                    'from': tx_details.get('from'),
                    'to': tx_details.get('to'),
                    'value': Decimal(tx_details.get('value')),
                    'is_valid': True
                }]
                return {
                    'hash': tx_details.get('hash'),
                    'success': True,
                    'inputs': [],
                    'outputs': [],
                    'transfers': transfer,
                    'block': 0,
                    'confirmations': self.estimate_confirmation_by_date(tx_date),
                    'fees': Decimal(tx_details.get('fees')),
                    'date': tx_date,
                    'raw': tx_details
                }
            return {'success': False}
        except AttributeError as e:
            raise ParseError(f'{self.symbol} parsing error tx_details response is {response}.') from e

    def validate_transaction_detail(self, tx_details: dict) -> bool:
        return (tx_details.get('hash')
                and tx_details.get('success') == 'SUCCESS_VALUE'
                and tx_details.get('type') == 'TRANSFER'
                and self.validate_tx_amount(Decimal(tx_details.get('value'))))
