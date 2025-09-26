import datetime


from exchange.base.models import Currencies
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class BitapsAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    """

    _base_url = 'https://api.bitaps.com'
    testnet_url = 'https://api.bitaps.com/{network}/testnet/v1/blockchain'

    currency = None
    symbol = ''

    rate_limit = 0.34
    back_off_time = 180

    supported_requests = {
        'get_tx_details': '/{network}/v1/blockchain/transaction/{hash}',
    }

    def get_name(self):
        return 'bitaps_api'

    def get_tx_details(self, tx_hash):
        response = self.request('get_tx_details', network=self.symbol.lower(), hash=tx_hash)

        if not response or not response.get('data').get('valid'):
            raise APIError(f'[{self.symbol} Bitaos API][Get Transaction details] unsuccessful')

        tx = self.parse_tx_details(response)
        return tx

    def parse_tx_details(self, tx_info):
        inputs = []
        input_addresses = []
        outputs = []
        confirmations = tx_info.get('data').get('confirmations')
        block_hash = tx_info.get('data').get('blockHash')
        timestamp = datetime.datetime.fromtimestamp(tx_info.get('data').get('time'))

        for input_ in list(tx_info.get('data').get('vIn').values()):
            inputs.append({
                'currency': self.currency,
                'address': input_.get('address'),
                'value': self.from_unit(input_.get('amount')),
                'type': input_.get('type'),
            })
            input_addresses.append(input_.get('address'))
        for output in list(tx_info.get('data').get('vOut').values()):
            if output.get('address') in input_addresses:
                continue
            outputs.append({
                'currency': self.currency,
                'address': output.get('address'),
                'value': self.from_unit(output.get('value')),
                'type': output.get('type'),
            })

        return {
            'hash': tx_info.get('data').get('txId'),
            'success': tx_info.get('data').get('valid'),
            'inputs': inputs,
            'outputs': outputs,
            'confirmations': confirmations,
            'block_hash': block_hash,
            'timestamp': timestamp,
            'raw': tx_info
        }


class BitcoinBitapsAPI(BitapsAPI):

    symbol = 'BTC'
    currency = Currencies.btc
    PRECISION = 8

