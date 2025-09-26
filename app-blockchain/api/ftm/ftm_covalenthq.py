import random

from django.conf import settings

from exchange.blockchain.api.commons.covalenthq import CovalenthqApi, CovalenthqResponseParser
from exchange.blockchain.contracts_conf import opera_ftm_contract_info, opera_ftm_contract_currency

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class FTMCovalenthqResponseParser(CovalenthqResponseParser):
    precision = 18
    currency = Currencies.ftm
    symbol = "FTM"

    @classmethod
    def contract_currency_list(cls):
        return opera_ftm_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return opera_ftm_contract_info.get(cls.network_mode)


class FtmCovalenthqApi(CovalenthqApi):
    parser = FTMCovalenthqResponseParser
    _base_url = 'https://api.covalenthq.com/v1/250'
    testnet_url = 'https://api.covalenthq.com/v1/4002/'
    symbol = 'FTM'
    cache_key = 'ftm'

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.COVALENT_API_KEYS)
