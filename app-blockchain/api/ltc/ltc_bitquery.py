import random

from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.commons.bitquery import (BitqueryApi,
                                                      BitqueryResponseParser,
                                                      BitqueryValidator)


class LTCResponseParser(BitqueryResponseParser):
    currency = Currencies.ltc
    validator = BitqueryValidator
    symbol = 'LTC'


class LtcBitqueryAPI(BitqueryApi):
    """
        coins: LTC
        API docs: https://graphql.bitquery.io/ide
        Explorer: https://explorer.bitquery.io/ltc
    """
    symbol = 'LTC'
    cache_key = 'ltc'
    currency = Currencies.ltc
    parser = LTCResponseParser
    GET_BLOCK_ADDRESSES_MAX_NUM = 10
    BITQUERY_NETWORK = 'litecoin'

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.BITQUERY_API_KEY)
