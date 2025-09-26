from decimal import Decimal

from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.blockcypher import BlockcypherAPI


class BtcBlockcypherAPI(BlockcypherAPI):
    symbol = 'BTC'
    currency = Currencies.btc
    PRECISION = 8
    min_valid_tx_amount = Decimal('0.0005')
