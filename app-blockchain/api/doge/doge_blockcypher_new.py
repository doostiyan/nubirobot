from decimal import Decimal

from django.conf import settings

from exchange.blockchain.api.commons.blockcypher import BlockcypherValidator, BlockcypherParser, BlockcypherApi

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class DogeBlockcypherParser(BlockcypherParser):
    precision = 8
    currency = Currencies.doge
    symbol = 'DOGE'


class DogeBlockcypherApi(BlockcypherApi):
    parser = DogeBlockcypherParser
    cache_key = 'doge'
    symbol = 'DOGE'
    USE_PROXY = True
