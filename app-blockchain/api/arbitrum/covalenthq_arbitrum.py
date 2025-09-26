import random

from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.commons.covalenthq import CovalenthqResponseValidator, CovalenthqResponseParser, \
    CovalenthqApi


class CovalenthqArbitrumResponseParser(CovalenthqResponseParser):
    validator = CovalenthqResponseValidator

    symbol = 'ETH'
    currency = Currencies.eth
    precision = 18


class CovalenthqArbitrumApi(CovalenthqApi):
    parser = CovalenthqArbitrumResponseParser

    _base_url = 'https://api.covalenthq.com/v1/42161'
    cache_key = 'arb'
    instance = None

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.ARBITRUM_COVALENTHQ_API_KEY)
