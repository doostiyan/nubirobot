import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings

from exchange.base.parsers import parse_utc_timestamp_ms
from exchange.blockchain.api.near.near_general import NearGeneralAPI
from exchange.blockchain.utils import APIError, ParseError


class NearOfficialAPI(NearGeneralAPI):
    """
    API Explorer: https://explorer.near.org
    """

    _base_url = 'https://explorer-backend-mainnet-prod-24ktefolwq-uc.a.run.app/'
    # another _base_url -> https://backend-mainnet-1713.onrender.com/

    supported_requests = {
        'get_transactions':
            'trpc/transaction.listByAccountId?batch=1&input={{"0":{{"accountId":"{address}","limit":10}}}}',
        'get_block_head': 'trpc/block.list?batch=1&input={{"0":{{"limit":1}}}}',
        'get_block': 'trpc/transaction.listByBlockHash?batch=1&input={{"0":{{"blockHash":"{hash}","limit":{limit}}}}}',
        'get_block_hash': 'trpc/block.byId?batch=1&input={{"0":{{"height":{block_height}}}}}',
        'get_tx_details': 'trpc/transaction.byHashOld?batch=1&input={{"0":{{"hash":"{tx_hash}"}}}}',
    }

    USE_PROXY = bool(not settings.IS_VIP)

    def get_name(self) -> str:
        return 'official_api'

    def get_txs(self, address: str) -> List[Dict[int, Dict[str, Any]]]:
        if not self.validate_address(address):
            return []
        response = self.request('get_transactions', address=address)
        transactions = []
        txs = response[0].get('result').get('data').get('items')
        for tx in txs:
            if self.validate_transaction(tx, address, 'incoming'):
                parsed_tx = self.parse_tx(tx, address)
                transactions.append(parsed_tx)
        return transactions

    def parse_tx(self, tx: Dict[str, Any], address: str) -> Dict[int, Dict[str, Any]]:
        try:
            tx_hash = tx.get('hash')
            from_address = self.parse_tx_sender(tx)
            to_address = self.parse_tx_receiver(tx)
            tx_block_height = tx.get('blockHash')
            tx_amount = self.from_unit(int(Decimal(tx.get('actions')[0].get('args').get('deposit'))))
            date = parse_utc_timestamp_ms(tx.get('blockTimestamp'))
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
                'confirmations': self.calculate_tx_confirmations(date),
                'direction': direction,
                'raw': tx
            }
        }

    def parse_tx_details(self, tx: List[Dict[str, Any]]) -> Dict[str, Any]:
        tx = tx[0].get('result').get('data')
        is_valid = self.validate_transaction_detail(tx)
        from_address = self.parse_tx_sender(tx)
        to_address = self.parse_tx_receiver(tx)
        if from_address == to_address:
            is_valid = False
        if not is_valid:
            return {
                'success': False,
            }
        date = parse_utc_timestamp_ms(tx.get('blockTimestamp'))
        transfer = [{
            'type': tx.get('actions')[0].get('kind'),
            'symbol': self.symbol,
            'currency': self.currency,
            'from': from_address,
            'to': to_address,
            'value': self.from_unit(int(Decimal(tx.get('actions')[0].get('args').get('deposit')))),
            'is_valid': is_valid
        }]
        return {
            'hash': tx.get('hash'),
            'success': is_valid and tx.get('status') == 'success',
            'inputs': [],
            'outputs': [],
            'transfers': transfer,
            'block': tx.get('blockHash'),
            'date': date,
            'confirmations': self.calculate_tx_confirmations(date),
            'fee': tx.get('outcome').get('gasBurnt') * 2,
            'raw': tx
        }

    def parse_block_head(self, response: List[Dict[str, Any]]) -> int:
        return response[0].get('result').get('data')[0].get('height')

    def get_block_hash(self, block_height: int) -> Tuple[str, int]:
        try:
            response = self.request('get_block_hash', block_height=block_height)
        except ConnectionError as e:
            raise APIError(
                f'{self.symbol} API: Failed to get block hash of block_height={block_height}, connection error') from e
        data = response[0].get('result').get('data') or {}
        return data.get('hash'), data.get('transactionsCount')

    def get_block_transactions(self, block_height: int) -> List[Dict[str, Any]]:
        try:
            block_hash, txs_count = self.get_block_hash(block_height)
            if not block_hash:
                return []
            if txs_count < 1:
                return []
            response = self.request('get_block', hash=block_hash, limit=100)
        except ConnectionError as e:
            raise APIError(
                f'{self.symbol} API: Failed to get txs of block_height={block_height}, connection error') from e
        return self.parse_block_transactions(response)

    def parse_block_transactions(self, response: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not response:
            raise APIError(f'{self.symbol} Get block API returns empty response')
        return response[0].get('result').get('data').get('items')

    def parse_transaction_data(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        try:
            tx_data = {
                'hash': tx.get('hash'),
                'from': self.parse_tx_sender(tx),
                'to': self.parse_tx_receiver(tx),
                'amount': self.from_unit(int(Decimal(tx.get('actions')[0].get('args').get('deposit')))),
                'currency': self.currency
            }
        except AttributeError as e:
            raise ParseError(f'{self.symbol} parsing error. tx is {tx}.') from e
        return tx_data

    def validate_transaction(self, tx: Dict[str, Any], address: Optional[str] = None,
                             tx_direction: Optional[str] = None) -> bool:
        try:
            tx_hash = tx.get('hash')
            if not tx_hash:
                return False
            status = tx.get('status')
            if status != 'success':
                return False
            actions_count = len(tx.get('actions'))
            if actions_count != 1:  # as we do not support multiple transfer
                return False
            tx_type = tx.get('actions')[0].get('kind')
            if tx_type != 'transfer':
                return False
            tx_amount = self.from_unit(int(Decimal(tx.get('actions')[0].get('args').get('deposit'))))
            if not self.validate_tx_amount(tx_amount):
                return False
        except AttributeError as e:
            raise ParseError(f'{self.symbol} parsing error Tx is {tx}.') from e
        if address and tx_direction:
            direction = self.get_tx_direction(tx, address)
            if not direction or direction != tx_direction:
                return False
        return True

    def validate_transaction_detail(self, details: Dict[str, Any]) -> bool:
        return self.validate_transaction(details)

    def parse_tx_sender(self, tx: Dict[str, Any]) -> str:
        return tx.get('signerId')

    def parse_tx_receiver(self, tx: Dict[str, Any]) -> str:
        return tx.get('receiverId')

    @classmethod
    def calculate_tx_confirmations(cls, tx_date: datetime) -> int:
        diff = (datetime.datetime.now(datetime.timezone.utc) - tx_date).total_seconds()
        return int(diff / 1.2)  # Near block time is 1 seconds, for more reliability we get it for '1.2'.
