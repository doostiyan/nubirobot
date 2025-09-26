import random
from decimal import Decimal

from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.commons.bitquery import (BitqueryApi,
                                                      BitqueryResponseParser,
                                                      BitqueryValidator)


class DogeBitqueryValidator(BitqueryValidator):
    min_valid_tx_amount = Decimal('1.00000000')


class DogeBitqueryResponseParser(BitqueryResponseParser):
    validator = DogeBitqueryValidator
    symbol = 'DOGE'
    currency = Currencies.doge


class DogeBitqueryAPI(BitqueryApi):
    """
        coins: DOGE
        API docs: https://graphql.bitquery.io/ide
        Explorer: https://explorer.bitquery.io/ltc
    """
    symbol = 'DOGE'
    cache_key = 'doge'
    currency = Currencies.doge
    parser = DogeBitqueryResponseParser
    GET_BLOCK_ADDRESSES_MAX_NUM = 10
    PAGINATION_OFFSET = 0
    BITQUERY_NETWORK = 'dogecoin'

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.BITQUERY_API_KEY)
