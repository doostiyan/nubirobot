import random

from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.contracts_conf import opera_ftm_contract_currency, opera_ftm_contract_info
from exchange.blockchain.api.common_apis.blockscan import BlockScanAPI


class FtmScanAPI(BlockScanAPI):
    """
    Fantom FtmScan API explorer.

    supported coins: FTM

    API docs: https://ftmscan.com/apis
    Explorer: https://ftmscan.com/
    """

    _base_url = 'https://api.ftmscan.com'
    testnet_url = 'https://api-testnet.ftmscan.com'
    symbol = 'FTM'
    currency = Currencies.ftm
    rate_limit = 0.2
    PRECISION = 18
    cache_key = 'ftm'

    @property
    def contract_currency_list(self):
        return opera_ftm_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return opera_ftm_contract_info.get(self.network)

    def get_api_key(self):
        return random.choice(settings.FTMSCAN_API_KEYS)
