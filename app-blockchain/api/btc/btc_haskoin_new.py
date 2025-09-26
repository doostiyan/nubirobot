from decimal import Decimal
from exchange.base.models import Currencies

from exchange.blockchain.api.commons.haskoin import HaskoinApi, HaskoinResponseParser, HaskoinValidator


class BitcoinHaskoinValidator(HaskoinValidator):
    min_valid_tx_amount = Decimal('0.0005')


class BitcoinHaskoinParser(HaskoinResponseParser):
    validator = BitcoinHaskoinValidator
    symbol = 'BTC'
    precision = 8
    currency = Currencies.btc

    @classmethod
    def convert_address(cls, address):
        return address


class BitcoinHaskoinAPI(HaskoinApi):
    parser = BitcoinHaskoinParser
    symbol = 'BTC'
    cache_key = 'btc'
