import random
from decimal import Decimal
from typing import Any, Optional

from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_iso_date
else:
    from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.near.near_general import NearGeneralAPI
from exchange.blockchain.utils import APIError, ParseError


class NearFigmentEnrichedAPI(NearGeneralAPI):
    """
    API doc: https://docs.figment.io/network-documentation/near/enriched-apis/indexer-api
    """
    rate_limit = 1.15  # 3m request per month, 10 request per second, 10 concurrent request
    get_txs_keyword = 'records'
    _base_url = 'https://near--indexer.datahub.figment.io/'
    supported_requests = {
        'get_balance': 'accounts/{address}',
        'get_block_head': 'height',
        'get_tx_details': 'transactions/{tx_hash}',
        'get_transactions': 'transactions?{tx_query_direction}={address}&'
                            'limit={pagination_limit}&page={pagination_page}',
        'get_block_txs': 'transactions?block_height={block_height}'
    }

    def get_name(self) -> str:
        return 'figment_api'

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.NEAR_FIGMENT_API_KEY)

    def get_header(self) -> dict:
        return {
            'Authorization': self.get_api_key()
        }

    def parse_balance(self, response: dict) -> Decimal:
        try:
            balance = self.from_unit(int(Decimal(response.get('amount'))))
        except TypeError as e:
            raise APIError(f'{self.symbol} API: Failed to get amount from balance response: {response}') from e
        if balance is None:
            raise APIError(f'{self.symbol} API: Failed to get address balance , balance response: {response}')
        return Decimal(balance)

    def parse_block_head(self, response: dict) -> Any:
        try:
            block_height = response.get('height')
        except AttributeError as e:
            raise ParseError(f'{self.symbol} get block head parsing error.') from e
        return block_height

    def parse_tx(self, tx: dict, address: str, block_head: int) -> dict:
        try:
            tx_hash = tx.get('hash')
            from_address = self.parse_tx_sender(tx)
            to_address = self.parse_tx_receiver(tx)
            tx_block_height = tx.get('height')
            tx_amount = self.from_unit(int(Decimal(tx.get('actions')[0].get('data').get('deposit'))))
            date = parse_iso_date(tx.get('time'))
            direction = self.get_tx_direction(tx, address)
        except AttributeError as e:
            raise ParseError(f'{self.symbol} parsing error Tx is {tx}.') from e
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
                'raw': tx
            }
        }

    def validate_transaction(self, tx: dict, address: Optional[str] = None, tx_direction: Optional[str] = None) -> bool:
        try:
            tx_hash = tx.get('hash')
            if not tx_hash:
                return False
            success = tx.get('success')
            if not success:
                return False
            actions_count = tx.get('actions_count')
            if actions_count != 1:  # as we do not support multiple transfer
                return False
            tx_type = tx.get('actions')[0].get('type')
            if tx_type not in self.valid_transfer_types:
                return False
            tx_amount = self.from_unit(int(Decimal(tx.get('actions')[0].get('data').get('deposit'))))
            if not self.validate_tx_amount(tx_amount):
                return False
        except AttributeError as e:
            raise ParseError(f'{self.symbol} parsing error Tx is {tx}.') from e
        if address and tx_direction:
            direction = self.get_tx_direction(tx, address)
            if not direction or direction != tx_direction:
                return False
        return True

    def parse_tx_details(self, tx: dict) -> dict:
        is_valid = self.validate_transaction_detail(tx)
        if not is_valid:
            return {
                'success': False,
            }
        try:
            block_head = self.get_block_head()
            tx_hash = tx.get('hash')
            sender = self.parse_tx_sender(tx)
            receiver = self.parse_tx_receiver(tx)
            tx_block = tx.get('height')
            tx_type = tx.get('actions')[0].get('type')
            tx_amount = self.from_unit(int(Decimal(tx.get('actions')[0].get('data').get('deposit'))))
            date = parse_iso_date(tx.get('time'))
            tx_denom = self.symbol
            fee = self.from_unit(int(tx.get('fee')))
            success = is_valid and tx.get('success')
        except AttributeError as e:
            raise ParseError(f'{self.symbol} parsing error tx_details response is {tx}.') from e
        transfer = [{
            'type': tx_type,
            'symbol': tx_denom,
            'currency': self.currency,
            'from': sender,
            'to': receiver,
            'value': tx_amount,
            'is_valid': is_valid
        }]
        return {
            'hash': tx_hash,
            'success': success,
            'inputs': [],
            'outputs': [],
            'transfers': transfer,
            'block': tx_block,
            'confirmations': block_head - tx_block,
            'fees': fee,
            'date': date,
            'raw': tx
        }

    def validate_transaction_detail(self, details: Any) -> bool:
        return self.validate_transaction(details)

    def parse_block_transactions(self, response: dict) -> Any:
        if not response:
            raise APIError(f'{self.symbol} Get block API returns empty response')
        return response.get(self.get_txs_keyword)

    def parse_transaction_data(self, tx: dict) -> dict:
        try:
            return {
                'hash': tx.get('hash'),
                'from': self.parse_tx_sender(tx),
                'to': self.parse_tx_receiver(tx),
                'amount': self.from_unit(int(Decimal(tx.get('actions')[0].get('data').get('deposit')))),
                'currency': self.currency
            }
        except AttributeError as e:
            raise ParseError(f'{self.symbol} parsing error. tx is {tx}.') from e

    def parse_tx_sender(self, tx: dict) -> str:
        return tx.get('sender')

    def parse_tx_receiver(self, tx: dict) -> str:
        return tx.get('receiver')
