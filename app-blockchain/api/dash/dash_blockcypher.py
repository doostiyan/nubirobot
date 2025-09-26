from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.blockcypher import BlockcypherAPI


class DashBlockcypherAPI(BlockcypherAPI):
    symbol = 'DASH'
    currency = Currencies.dash
    PRECISION = 8
