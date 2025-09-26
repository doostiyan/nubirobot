import random

from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.blockscan import BlockScanAPI
from exchange.blockchain.contracts_conf import BEP20_contract_currency, BEP20_contract_info


class BscScanAPI(BlockScanAPI):
    """
    coins: Binance coin
    API docs: https://bscscan.com/apis
    :exception ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut
    """

    _base_url = 'https://api.bscscan.com'
    testnet_url = 'https://api-testnet.bscscan.com'
    currency = Currencies.bnb
    symbol = 'BSC'
    rate_limit = 0.2  # (5 req/sec)
    PRECISION = 18
    cache_key = 'bsc'
    USE_PROXY = True

    def get_api_key(self):
        return random.choice(settings.BSCSCAN_API_KEY)

    @property
    def contract_currency_list(self):
        return BEP20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return BEP20_contract_info.get(self.network)
