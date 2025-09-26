from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class DogeBlockChairApi(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: DogeCoin
    """

    _base_url = 'https://api.blockchair.com/dogecoin'
    symbol = 'DOGE'
    currency = Currencies.doge
    active = True
    PRECISION = 8
    USE_PROXY = False

    supported_requests = {
        'get_tx_details': '/dashboards/transaction/{tx_hash}',
        'get_block_head': '/stats'
    }

    def get_name(self):
        return 'doge_block_chair_api'

    def get_block_head(self):
        response = self.request('get_block_head')
        # General Validator
        if not response:
            raise APIError('[DogeBlockChairApi][GetBlockHead] Response is None')
        if 'data' not in response:
            raise APIError('[DogeBlockChairApi][GetBlockHead] Response without data')
        # Block Head Validator
        if not response.get('data').get('best_block_height'):
            raise APIError('[DogeBlockChairApi][GetBlockHead] Empty field')

        return int(response.get('data').get('best_block_height'))

    def get_tx_details(self, tx_hash):
        response = self.request('get_tx_details', tx_hash=tx_hash)
        # General Validator
        if not response:
            raise APIError('[DogeBlockChairApi][GetTxDetails] Response is None')
        if 'data' not in response:
            raise APIError('[DogeBlockChairApi][GetTxDetails] Response without data')
        # Tx details Validator
        if not response.get('data') or not response.get('data').get(tx_hash):
            return {'success': False}

        return self.parse_tx_details(response.get('data').get(tx_hash))

    def parse_tx_details(self, tx, tx_hash=None):
        block_head = self.get_block_head()
        inputs = []
        outputs = []
        input_addresses = []
        for input_ in tx.get('inputs'):
            input_addresses.append(input_.get('recipient'))
            inputs.append(
                {
                    'currency': self.currency,
                    'address': input_.get('recipient'),
                    'value': self.from_unit(input_.get('value'), precision=self.PRECISION),
                    'type': input_.get('type'),
                }
            )
        for output in tx.get('outputs'):
            if output.get('recipient') in input_addresses or output.get('type') != 'pubkeyhash':
                continue
            outputs.append(
                {
                    'currency': self.currency,
                    'address': output.get('recipient'),
                    'value': self.from_unit(output.get('value'), precision=self.PRECISION),
                    'type': output.get('type'),
                }
            )
        success = True
        if tx.get('transaction').get('block_id') == -1:
            success = False
        date = tx.get('transaction').get('time').split(' ')
        return {
            'hash': tx.get('transaction').get('hash'),
            'success': success,
            'inputs': inputs,
            'outputs': outputs,
            'block': tx.get('transaction').get('block_id'),
            'confirmations': block_head - tx.get('transaction').get('block_id'),
            'fees': self.from_unit(tx.get('transaction').get('fee'), precision=self.PRECISION),
            'date': parse_iso_date(date[0] + 'T' + date[1] + 'Z'),
            'raw': tx
        }
