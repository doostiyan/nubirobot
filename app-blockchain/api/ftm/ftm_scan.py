import random

from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
from exchange.blockchain.api.commons.blockscan import BlockScanAPI
from exchange.blockchain.api.commons.blockscan import BlockScanResponseParser
from exchange.blockchain.contracts_conf import opera_ftm_contract_info, opera_ftm_contract_currency


class FTMResponseResponseParser(BlockScanResponseParser):
    symbol = "FTM"
    precision = 18
    currency = Currencies.ftm

    @classmethod
    def contract_info_list(cls):
        return opera_ftm_contract_info.get(cls.network_mode)

    @classmethod
    def contract_currency_list(cls):
        return opera_ftm_contract_currency.get(cls.network_mode)


class FtmScanApi(BlockScanAPI):
    """
    Fantom FtmScan API explorer.

    supported coins: FTM

    API docs: https://ftmscan.com/apis
    Explorer: https://ftmscan.com/
    """
    parser = FTMResponseResponseParser
    testnet_url = 'https://api-testnet.ftmscan.com'
    symbol = 'FTM'
    cache_key = "ftm"
    rate_limit = 0.2
    chain_id = 250

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.FTMSCAN_API_KEYS)
