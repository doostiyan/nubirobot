from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
from exchange.blockchain.api.commons.blockcypher import BlockcypherApi, BlockcypherParser


class LiteCoinBlockcypherResponseParser(BlockcypherParser):
    symbol = 'LTC'
    currency = Currencies.ltc
    precision = 8


class LiteCoinBlockcypherAPI(BlockcypherApi):
    parser = LiteCoinBlockcypherResponseParser
    symbol = 'LTC'
    cache_key = 'ltc'
    instance = None
