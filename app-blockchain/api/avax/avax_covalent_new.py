import random
from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.contracts_conf import avalanche_ERC20_contract_info, avalanche_ERC20_contract_currency
from exchange.blockchain.api.commons.covalenthq import CovalenthqApi, CovalenthqResponseParser


class AvalancheCovalentParser(CovalenthqResponseParser):
    precision = 18
    symbol = 'AVAX'
    currency = Currencies.avax

    @classmethod
    def contract_currency_list(cls):
        return avalanche_ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return avalanche_ERC20_contract_info.get(cls.network_mode)


class AvalancheCovalentAPI(CovalenthqApi):
    parser = AvalancheCovalentParser
    _base_url = 'https://api.covalenthq.com/v1/43114'
    testnet_url = 'https://api.covalenthq.com/v1/43113'
    instance = None
    symbol = 'AVAX'
    cache_key = 'avax'

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.COVALENT_API_KEYS)
