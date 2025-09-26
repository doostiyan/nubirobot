from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.blockcypher import BlockcypherAPI


class DogeBlockcypherAPI(BlockcypherAPI):
    symbol = 'DOGE'
    currency = Currencies.doge
    PRECISION = 8
    USE_PROXY = False
