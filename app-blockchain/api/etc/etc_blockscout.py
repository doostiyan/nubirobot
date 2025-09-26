from typing import Any, Dict, List

from exchange.base.models import Currencies
from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


class ETCBlockscoutAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: EthereumClassic
    API docs: https://blockscout.com/etc/mainnet/api-docs
    """
    _base_url = 'https://blockscout.com/etc/mainnet/api'
    symbol = 'ETC'
    currency = Currencies.etc
    PRECISION = 18
    rate_limit = 0.006  # 10000 req/m

    supported_requests = {
        'get_transaction': '?module=transaction&action=gettxinfo&txhash={transaction_hash}'
    }

    def get_name(self) -> str:
        return 'blockscout_api'

    def get_tx_details(self, tx_hash: str) -> Dict[str, Any]:
        tx_hash = tx_hash if tx_hash.startswith('0x') else '0x' + tx_hash
        response = self.request('get_transaction', transaction_hash=tx_hash)
        if response.get('message') != 'OK' or response.get('status') != '1':
            raise APIError('[ETCBlockscoutAPI][GetTransactionDetails] Response is not ok.')

        return self.parse_tx_details(response.get('result'))

    def decode_tx_input_data(self, input_data: str) -> Dict[str, Any]:
        return {
            'value': int(input_data[74:138], 16),
            'to': '0x' + input_data[34:74]
        }

    def parse_tx_details(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        transfers: List[Dict[str, Any]] = []
        is_valid = False
        tx_input = tx.get('input')
        if self.validate_transaction(tx):
            is_valid = True
            if tx_input == '0x':
                transfers.append({
                    'type': 'MainCoin',
                    'symbol': self.symbol,
                    'currency': self.currency,
                    'from': tx.get('from'),
                    'to': tx.get('to'),
                    'value': self.from_unit(int(tx.get('value'))),
                    'is_valid': is_valid,
                })
        return {
            'hash': tx.get('hash'),
            'success': tx.get('success'),
            'is_valid': tx.get('success') and is_valid,
            'inputs': [],
            'outputs': [],
            'transfers': transfers,
            'block': tx.get('blockNumber'),
            'confirmations': tx.get('confirmations'),
            'date': parse_utc_timestamp(int(tx.get('timeStamp'))),
            'raw': tx,
        }

    @staticmethod
    def validate_transaction(tx_info: Dict[str, Any]) -> bool:
        valid_input_data_length: int = 138
        if tx_info.get('input') == '0x' or tx_info.get('input') == '0x0000000000000000000000000000000000000000':
            return True
        if tx_info.get('input')[0:10] == '0xa9059cbb' and len(tx_info.get('input')) == valid_input_data_length:
            return True
        return False
