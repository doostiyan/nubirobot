import random

from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.commons.bitquery import (BitqueryApi,
                                                      BitqueryResponseParser,
                                                      BitqueryValidator)


class BTCResponseParser(BitqueryResponseParser):
    currency = Currencies.btc
    validator = BitqueryValidator
    symbol = 'BTC'


class BtcBitqueryAPI(BitqueryApi):
    """
        coins: BTC
        API docs: https://graphql.bitquery.io/ide
        Explorer: https://explorer.bitquery.io/ltc
    """
    symbol = 'BTC'
    cache_key = 'btc'
    GET_BLOCK_ADDRESSES_MAX_NUM = 2
    currency = Currencies.btc
    parser = BTCResponseParser
    BITQUERY_NETWORK = 'bitcoin'

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.BITQUERY_API_KEY)
