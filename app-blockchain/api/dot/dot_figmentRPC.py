import json
import random

from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.utils import BlockchainUtilsMixin
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI


class DotFigmentRPC(NobitexBlockchainBlockAPI, BlockchainUtilsMixin):
    """
    Subscan API explorer.

    supported coins: dot
    API docs: https://polkadot.js.org/docs/substrate/rpc/
    Explorer: https://polkadot.api.subscan.io
    """
    _base_url = 'https://polkadot--rpc.datahub.figment.io'
    testnet_url = 'https://polkadot-westend--rpc.datahub.figment.io/'
    symbol = 'DOT'
    currency = Currencies.dot
    rate_limit = 1.15  # 3m request per month, 10 request per second, 10 concurrent request
    PRECISION = 10
    cache_key = 'dot'

    supported_requests = {
        'get_block_head': '',
    }

    def get_name(self):
        return 'figment_rpc_api'

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.DOT_FIGMENTRPC_API_KEY)

    def get_header(self):
        return {
            'Authorization': self.get_api_key(),
            'Content-Type': 'application/json'
        }

    def get_block_head(self):
        payload = {
            'jsonrpc': '2.0',
            'method': 'chain_getBlock',
            'id': 1
        }
        response = self.request('get_block_head', headers=self.get_header(), body=json.dumps(payload))
        block_height = response.get('result').get('block').get('header').get('number')
        block_height = int(block_height, 16)
        return block_height

    def get_latest_block(self):
        pass
