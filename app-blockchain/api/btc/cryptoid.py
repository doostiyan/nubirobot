from decimal import Decimal

from django.conf import settings

from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class CryptoidAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: Bitcoin
    doc: https://chainz.cryptoid.info/api.dws
    """

    _base_url = 'https://chainz.cryptoid.info'
    symbol = 'BTC'

    active = True

    rate_limit = 10
    max_items_per_page = 1000
    page_offset_step = None
    confirmed_num = None
    PRECISION = 8
    XPUB_SUPPORT = False

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/75.0'
    } if not settings.IS_VIP else {
        'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/109.0'
    }

    supported_requests = {
        'get_balances': '/btc/api.dws?q=getbalances&key={api_key}',
        'get_transactions': '/v1/blockchain/address/{address}'
    }

    def get_name(self):
        return 'cryptoid_api'

    def get_balances(self, addresses):
        for address in addresses:
            self.validate_address(address)
        api_key = '98c934d7044d' if not settings.IS_VIP else '3d9a79a42637'
        response = self.request('get_balances', json=list(addresses), headers=self.headers,
                                api_key=api_key, force_post=True)
        if response is None:
            raise APIError("[CryptoidAPI][Get Balances] response is None")
        balances = []
        for addr, balance in response.items():
            balance = Decimal(balance or '0')
            balances.append({
                'address': addr,
                'amount': balance,
            })
        return balances
