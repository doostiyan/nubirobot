from decimal import Decimal
import datetime

from django.conf import settings

from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class SochainAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: Litecoin, Doge, Bitcoin
    API docs: https://sochain.com/api
    """

    _base_url = 'https://chain.so/api/v3'
    testnet_url = 'https://chain.so/api/v3'

    currency = None

    active = True

    rate_limit = 0
    max_items_per_page = 1000
    page_offset_step = None
    confirmed_num = None
    XPUB_SUPPORT = False
    USE_PROXY = True if not settings.IS_VIP else False

    supported_requests = {
        'get_balance': '/balance/{network}/{address}',
        'get_tx_details': '/transaction/{network}/{tx_hash}',
    }

    def get_name(self):
        return 'sochain_api'

    def get_balance(self, address):
        self.validate_address(address)
        network = self.symbol
        if self.network == 'testnet':
            network = self.symbol + 'TEST'
        response = self.request('get_balance', address=address, network=network)

        if not response:
            raise APIError(f'[SochainAPI][{self.symbol}][Get Balance] response is None')
        if response.get('status') != 'success':
            raise APIError(f'[SochainAPI][{self.symbol}][Get Balance] unsuccessful')

        balance = response['data']
        return {
            'address': address,
            'network': balance.get('network'),
            'amount': Decimal(balance.get('confirmed') or '0'),
            'unconfirmed_balance': Decimal(balance.get('unconfirmed') or '0'),
        }

    def get_tx_details(self, tx_hash):
        try:
            response = self.request('get_tx_details', network=self.symbol, tx_hash=tx_hash)
        except Exception as e:
            raise APIError(f'[{self.symbol} sochain API][Get Transaction details] unsuccessful: {e}')

        if (not response) or (response.get('status') != 'success'):
            raise APIError(f'[{self.symbol} sochain API][Get Transaction details] unsuccessful')

        tx = self.parse_tx_details(response)
        return tx

    def parse_tx_details(self, tx_info):
        inputs = []
        input_addresses = []
        outputs = []
        confirmations = tx_info.get('data').get('confirmations')
        block_hash = tx_info.get('data').get('blockhash')
        timestamp = datetime.datetime.fromtimestamp(tx_info.get('data').get('time'))

        for input_ in tx_info.get('data').get('inputs'):
            address = self.convert_address(input_.get('address'))
            inputs.append({
                'currency': self.currency,
                'address': address,
                'value': Decimal(input_.get('value')),
                'type': input_.get('type'),
            })
            input_addresses.append(address)
        for output in tx_info.get('data').get('outputs'):
            address = self.convert_address(output.get('address'))
            if address in input_addresses:
                continue
            outputs.append({
                'currency': self.currency,
                'address': address,
                'value': Decimal(output.get('value')),
                'type': output.get('type'),
            })

        return {
            'hash': tx_info.get('data').get('txid'),
            'success': tx_info.get('status') == 'success',
            'inputs': inputs,
            'outputs': outputs,
            'confirmations': confirmations,
            'block_hash': block_hash,
            'timestamp': timestamp,
            'raw': tx_info
        }

    @classmethod
    def convert_address(cls, address):
        return address


