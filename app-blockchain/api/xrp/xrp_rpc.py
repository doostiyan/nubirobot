import json

from exchange.base.logging import report_event
from exchange.base.models import Currencies
from exchange.base.parsers import parse_utc_timestamp_from_2000
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class RippleRpcAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: Doge
    """

    _base_url = 'https://xrplcluster.com'
    symbol = 'XRP'

    rate_limit = 0
    max_items_per_page = 200
    page_offset_step = None
    confirmed_num = 12
    PRECISION = 6
    XPUB_SUPPORT = False
    USE_PROXY = False

    supported_requests = {
        'get_txs': '',
    }

    currency = Currencies.xrp

    def get_name(self):
        return 'rpc_api'

    def get_txs(self, address, offset=0, limit=50, unconfirmed=False, tx_direction_filter=''):
        """ Get account transaction from Solidity node

        :param contract_info: contract you want to
        :param offset: Fingerprint in previous transaction result
        :param limit: Limit in the number of transaction in each response
        :param unconfirmed: False|True. True if you want to return unconfirmed transactions too.
        :param tx_type: normal|trc20|all. If you set all return both normal and trc20 transactions.
        :return: List of transactions
        """
        self.validate_address(address)
        txs_result = self._get_txs(address, offset=offset, limit=limit, unconfirmed=unconfirmed)

        result = []
        txs = txs_result['transactions']
        max_ledger = int(txs_result['max_ledger'])
        for tx in txs:
            parsed_tx = self.parse_tx(tx=tx, address=address, max_ledger=max_ledger)
            if parsed_tx is not None:
                result.append(parsed_tx)
        return result

    def _get_txs(self, address, offset=0, limit=200, unconfirmed=False):
        data = {
            "method": "account_tx",
            "params": [
                {
                    "account": address,
                    "binary": False,
                    "forward": False,
                    "ledger_index_max": -1,
                    "ledger_index_min": -1,
                    "limit": limit
                }
            ]
        }

        headers = {'content-type': 'application/json'}
        response = self.request('get_txs', body=json.dumps(data), headers=headers)
        if not response:
            raise APIError("[XRPRPC][Get Transactions] response is None")
        if 'result' not in response:
            raise APIError("[XRPRPC][Get Transactions] response without result")
        transactions = response['result']['transactions']
        return {
            'transactions': transactions,
            'max_ledger':  response['result']['ledger_index_max']
        }

    def parse_tx(self, tx, address, max_ledger, tx_type='all', contract_info=None):
        tx_result = tx.get('validated') or False
        if not tx_result or tx.get('meta').get('TransactionResult') != 'tesSUCCESS':
            return None

        tx_data = tx.get('tx')
        tx_meta = tx.get('meta')

        if tx_data.get('TransactionType') != 'Payment':
            return None

        delivered_amount = tx_meta.get('delivered_amount')
        if type(delivered_amount) is dict:
            return None
        delivered_amount = self.from_unit(int(delivered_amount))

        if not delivered_amount:
            # report_event('[XRPRPC:get_txs] Received transaction does not have delivered amount')
            return None

        from_address = tx_data.get('Account')
        to_address = tx_data.get('Destination')
        to_tag = tx_data. get('DestinationTag')
        tx_hash = tx_data.get('hash')
        confirmations = max_ledger - int(tx_data['ledger_index'])

        if address == to_address:
            direction = 'incoming'
        elif address == from_address:
            direction = 'outgoing'
        else:
            return None

        if direction == 'outgoing':
            delivered_amount = -delivered_amount

        return {self.currency: {
            'date': parse_utc_timestamp_from_2000(tx_data['date']),
            'from_address': from_address,
            'to_address': to_address,
            'memo': to_tag,
            'amount': delivered_amount,
            'hash': tx_hash,
            'confirmations': confirmations,
            'is_error': False,
            'type': 'normal',
            'kind': 'transaction',
            'direction': direction,
            'status': 'confirmed' if confirmations > self.confirmed_num else 'unconfirmed',
            'raw': tx
        }}

    def get_tx_details(self, tx_hash):
        data = {
            "method": "tx",
            "params": [
                {
                    "transaction": tx_hash,
                    "binary": False,
                }
            ]
        }

        headers = {'content-type': 'application/json'}
        response = self.request('', body=json.dumps(data), headers=headers)
        if not response:
            raise APIError("[XRPRPC][Get Transaction] response is None")
        if 'result' not in response:
            raise APIError("[XRPRPC][Get Transaction] response without result")
        if response.get('result').get('status') == 'error':
            raise APIError(f"[XRPRPC][Get Transaction] {response.get('result').get('error')}")
        parsed_tx = self.parse_tx_details(response.get('result'))
        return parsed_tx

    def parse_tx_details(self, tx_info):
        transfers = []
        is_valid = False
        success = False
        memo = ''
        if tx_info.get('validated') and tx_info.get('status') == 'success':
            if tx_info.get('meta').get('delivered_amount') and tx_info.get('meta').get(
                    'TransactionResult') == 'tesSUCCESS':
                success = True
        if tx_info.get('TransactionType') == 'Payment' and type(tx_info.get('meta', {}).get('delivered_amount')) is str \
            and success:
            value = tx_info.get('meta', {}).get('delivered_amount')
            memo = tx_info.get('DestinationTag') or ''
            is_valid = True
            transfers = [{
                'type': 'MainCoin',
                'symbol': self.symbol,
                'currency': self.currency,
                'from': tx_info.get('Account'),
                'to': tx_info.get('Destination'),
                'value': self.from_unit(int(value)),
                'is_valid': is_valid
            }]
        return {
            'hash': tx_info.get('hash'),
            'success': success,
            'is_valid': is_valid,
            'inputs': [],
            'outputs': [],
            'transfers': transfers,
            'memo': memo,
            'block': int(tx_info.get('ledger_index')),
            'fees': self.from_unit(int(tx_info.get('Fee'))),
            'date': parse_utc_timestamp_from_2000(tx_info['date']),
        }

