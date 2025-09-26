import datetime

from exchange.base.models import Currencies
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class HaskoinAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: BTC
    """

    _base_url = 'https://api.haskoin.com'
    symbol = ''
    currency = None

    supported_requests = {
        'get_tx_details': '/{network}/transaction/{hash}',
    }

    def get_name(self):
        return '{}_haskoin'.format(self.symbol.lower())

    def get_tx_details(self, tx_hash):
        try:
            response = self.request('get_tx_details', network=self.symbol.lower(), hash=tx_hash)
        except Exception as e:
            raise APIError(f'[{self.symbol} HaskoinAPI][Get Transaction details] unsuccessful: {e}')

        tx = self.parse_tx_details(response, tx_hash)
        return tx

    def parse_tx_details(self, tx_info, tx_hash):
        inputs = []
        outputs = []
        input_addresses = []
        success = not tx_info.get('deleted') and not tx_info.get('rbf')
        for input_ in tx_info.get('inputs'):
            inputs.append({
                'currency': self.currency,
                'address': self.convert_address(input_.get('address')),
                'value': self.from_unit(input_.get('value') or 0),
                'is_valid': success
            })
            input_addresses.append(input_.get('address'))
        for output in tx_info.get('outputs'):
            if output.get('address') in input_addresses:
                continue
            outputs.append({
                'currency': self.currency,
                'address': self.convert_address(output.get('address')),
                'value': self.from_unit(output.get('value')),
                'is_valid': success
            })

        return {
            'hash': tx_hash,
            'success': success,
            'inputs': inputs,
            'outputs': outputs,
            'transfers': [],
            'block': tx_info.get('block').get('height'),
            'confirmations': 0,
            'fees': self.from_unit(tx_info.get('fee')),
            'date': datetime.datetime.fromtimestamp(tx_info.get('time')),
            'raw': tx_info,
        }

    def convert_address(self, address):
        return address


class BitcoinHaskoinAPI(HaskoinAPI):

    symbol = 'BTC'
    currency = Currencies.btc
    PRECISION = 8
