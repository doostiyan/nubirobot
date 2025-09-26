from decimal import Decimal

from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


# unreliable API. better not to use
class LitecoinnetAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: Litecoin
    """

    _base_url = 'http://explorer.litecoin.net/chain/Litecoin/q'
    symbol = 'LTC'

    active = True

    rate_limit = 0
    max_items_per_page = 1000
    page_offset_step = None
    confirmed_num = None
    PRECISION = 8
    XPUB_SUPPORT = False

    supported_requests = {
        'get_balance': '/addressbalance/{address}',
    }

    def get_name(self):
        return 'litecoin_api'

    def get_balance(self, address):
        self.validate_address(address)
        response = self.request('get_balance', address=address)
        if response is None:
            raise APIError("[LitecoinnetAPI][Get Balance] response is None")
        return{
            'amount': Decimal(str(response)),
        }
