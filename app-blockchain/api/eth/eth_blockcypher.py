from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.blockcypher import BlockcypherAPI


class EthBlockcypherAPI(BlockcypherAPI):
    symbol = 'ETH'
    currency = Currencies.eth
    PRECISION = 18
