from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.blockbook import BlockbookAPI


class TrxBlockbookAPI(BlockbookAPI):
    _base_url = 'https://blockbook-tron.tronwallet.me'
    USE_PROXY = bool(not settings.IS_VIP)
    TOKEN_NETWORK = True
    symbol = 'TRX'
    PRECISION = 6
    currency = Currencies.trx
    cache_key = 'trx'
    # TODO: proper parent functions to support for tron like other coins
