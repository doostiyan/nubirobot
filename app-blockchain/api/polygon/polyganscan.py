import random

from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.blockscan import BlockScanAPI
from exchange.blockchain.contracts_conf import polygon_ERC20_contract_info, polygon_ERC20_contract_currency


class PolygonScanAPI(BlockScanAPI):
    """
    coins: Matic coin
    API docs: https://polygonscan.com/apis
    :exception ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut
    """

    _base_url = 'https://api.polygonscan.com'
    testnet_url = 'https://mumbai.polygonscan.com'
    currency = Currencies.pol
    symbol = 'MATIC'
    rate_limit = 0.2  # (5 req/sec)
    PRECISION = 18
    cache_key = 'matic'
    USE_PROXY = True

    def get_api_key(self):
        return random.choice(settings.POLYGANSCAN_API_KEY)

    @property
    def contract_currency_list(self):
        return polygon_ERC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return polygon_ERC20_contract_info.get(self.network)
