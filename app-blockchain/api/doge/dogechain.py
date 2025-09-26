from decimal import Decimal
import datetime

from exchange.base.models import Currencies
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class DogechainAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: Doge
    """

    _base_url = 'https://dogechain.info'
    symbol = 'DOGE'
    currency = Currencies.doge

    active = True

    rate_limit = 0
    max_items_per_page = 1000
    page_offset_step = None
    confirmed_num = None
    PRECISION = 8
    USE_PROXY = False
    XPUB_SUPPORT = False

    supported_requests = {
        'get_balance': '/api/v1/address/balance/{address}',
        'get_balance_simple': '/chain/Dogecoin/q/addressbalance/{address}',
        'get_tx_details': '/api/v1/transaction/{tx_hash}'
    }

    def get_name(self):
        return 'dogechain_api'

    def get_balance_simple(self, address):
        self.validate_address(address)
        response = self.request('get_balance_simple', address=address)
        if response is None:
            raise APIError("[DogechainAPI][Get Balance] response is None")
        return{
            'amount': Decimal(str(response)),
        }

    def get_balance(self, address):
        self.validate_address(address)
        response = self.request('get_balance', address=address)
        if response is None:
            raise APIError("[DogechainAPI][Get Balance] response is None")
        if response.get('success') != 1:
            raise APIError("[DogechainAPI][Get Balance] unsuccessful")
        balance = response.get('balance')
        return {
            'amount': Decimal(balance),
        }

    def get_tx_details(self, tx_hash):
        try:
            response = self.request('get_tx_details', tx_hash=tx_hash)
        except Exception as e:
            raise APIError("[DOGE dogechain API][Get Transaction details] unsuccessful\nError:{}".format(e))

        tx = self.parse_tx_details(response)
        return tx

    def parse_tx_details(self, tx_info):
        inputs = []
        outputs = []
        input_addesses = []
        success = tx_info.get('success') == 1
        tx_info = tx_info.get('transaction')
        for inp in tx_info.get('inputs'):
            input_addesses.append(inp.get('address'))
            inputs.append(
                {
                    'currency': self.currency,
                    'address': inp.get('address'),
                    'value': Decimal(inp.get('value')),
                    'type': inp.get('type'),
                }
            )
        for output in tx_info.get('outputs'):
            if output.get('address') in input_addesses or output.get('type') != 'pubkeyhash':
                continue
            outputs.append(
                {
                    'currency': self.currency,
                    'address': output.get('address'),
                    'value': Decimal(output.get('value')),
                    'type': output.get('type'),
                }
            )
        confirmations = tx_info.get('confirmations')
        timestamp = datetime.datetime.fromtimestamp(tx_info.get('time'))

        return {
            'hash': tx_info.get('hash'),
            'success': success,
            'inputs': inputs,
            'outputs': outputs,
            'block': tx_info.get('block_hash'),
            'confirmations': confirmations,
            'fees': Decimal(tx_info.get('fee')),
            'date': timestamp,
            'raw': tx_info,
        }
