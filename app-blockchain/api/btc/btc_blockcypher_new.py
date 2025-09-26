from decimal import Decimal
from exchange.base.models import Currencies

from exchange.blockchain.api.commons.blockcypher import BlockcypherApi, BlockcypherParser, BlockcypherValidator


class BitcoinBlockcypherValidator(BlockcypherValidator):
    min_valid_tx_amount = Decimal('0.0005')


class BitcoinBlockcypherParser(BlockcypherParser):
    validator = BitcoinBlockcypherValidator
    symbol = 'BTC'
    currency = Currencies.btc
    precision = 8


class BitcoinBlockcypherAPI(BlockcypherApi):
    parser = BitcoinBlockcypherParser
    symbol = 'BTC'
    cache_key = 'btc'
