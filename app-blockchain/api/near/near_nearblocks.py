from decimal import Decimal
from typing import Optional

from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_utc_timestamp_nanosecond
else:
    from exchange.base.parsers import parse_utc_timestamp_nanosecond
from exchange.blockchain.api.near.near_general import NearGeneralAPI
from exchange.blockchain.utils import APIError, ParseError


class NearBlocksAPI(NearGeneralAPI):
    """
    API Doc: https://nearblocks.io/rest-api
    """
    _base_url = 'https://nearblocks.io/api/'
    get_txs_keyword = 'txns'
    supported_requests = {
        'get_balance': 'account/balance?address={address}',
        'get_block_head': 'blocks?limit=1&offset=0',
        'get_tx_details': 'txn?hash={tx_hash}',
        'get_transactions': 'account/txns?address={address}&limit={pagination_limit}&offset=={pagination_offset}'
    }

    def get_name(self) -> str:
        return 'nearblocks_api'

    def parse_balance(self, response: dict) -> Decimal:
        balance: Optional[str] = response.get('balance')
        if balance is None:
            raise APIError(f'{self.symbol} API: Failed to get address balance , balance response: {response}')
        return Decimal(balance.replace(',', ''))

    def parse_block_head(self, response: dict) -> int:
        try:
            return int(response.get('blocks')[0].get('block_height'))
        except AttributeError as e:
            raise ParseError(f'{self.symbol} get block head parsing error.') from e

    def validate_transaction(self, tx: dict, address: Optional[str] = None) -> bool:
        # Dose not validate tx status as it is not available in get_txs response
        try:
            tx_type = tx.get('type')
            if tx_type not in self.valid_transfer_types:
                return False
            tx_amount = self.from_unit(int(Decimal(tx.get('deposit_value'))))
            if not self.validate_tx_amount(tx_amount):
                return False
            if address:
                direction = self.get_tx_direction(tx, address)
                if not direction:
                    return False
                tx['direction'] = direction
        except AttributeError as e:
            raise ParseError(f'{self.symbol}: parsing error Tx is {tx}.') from e
        return True

    def parse_tx(self, tx: dict, address: str, block_head: int) -> dict:
        try:
            tx_hash = tx.get('transaction_hash')
            from_address = self.parse_tx_sender(tx)
            to_address = self.parse_tx_receiver(tx)
            tx_block_height = tx.get('height')
            tx_amount = self.from_unit(int(Decimal(tx.get('deposit_value'))))
            date = parse_utc_timestamp_nanosecond(tx.get('block_timestamp'))
            direction = tx.get('direction')
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
                'raw': ''
            }
        }

    def validate_transaction_detail(self, details: dict) -> bool:
        # Dose not validate tx type as it is not available in transaction_detail response
        try:
            tx_status = details.get('status')
            if tx_status == 'Failed':
                return False
            tx_amount = self.from_unit(int(Decimal(details.get('deposit_value'))))
            if not self.validate_tx_amount(tx_amount):
                return False
        except AttributeError as e:
            raise ParseError(f'{self.symbol}: parsing error Tx is {details}.') from e
        return True

    def parse_tx_details(self, response: dict) -> dict:
        tx = response.get('txn')
        is_valid = self.validate_transaction_detail(tx)
        if not is_valid:
            return {
                'success': False,
            }
        try:
            tx_hash = tx.get('transaction_hash')
            success = tx.get('status') == 'Succeeded'
            tx_block = tx.get('height')
            block_head = self.get_block_head()
            date = parse_utc_timestamp_nanosecond(tx.get('block_timestamp'))
            fee = self.from_unit(int(tx.get('transaction_fee')))  # yokto to Near
            transfer = [{
                'type': '',
                'symbol': self.symbol,
                'currency': self.currency,
                'from': self.parse_tx_sender(tx),
                'to': self.parse_tx_receiver(tx),
                'value': self.from_unit(int(Decimal(tx.get('deposit_value')))),
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
                'raw': ''
            }
        except AttributeError as e:
            raise ParseError(f'{self.symbol}: parsing error tx_details response is {response}.') from e

    def parse_tx_sender(self, tx: dict) -> str:
        return tx.get('from')

    def parse_tx_receiver(self, tx: dict) -> str:
        return tx.get('to')
