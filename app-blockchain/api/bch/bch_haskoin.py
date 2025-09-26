from decimal import Decimal

from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.commons.haskoin import HaskoinApi, HaskoinResponseParser, HaskoinValidator


class BitcoinCashHaskoinValidator(HaskoinValidator):
    min_valid_tx_amount = Decimal('0.003')
    precision = 8


class BitcoinCashHaskoinResponseParser(HaskoinResponseParser):
    validator = BitcoinCashHaskoinValidator
    symbol = 'BCH'
    currency = Currencies.bch
    precision = 8


class BitcoinCashHaskoinApi(HaskoinApi):
    parser = BitcoinCashHaskoinResponseParser
    cache_key = 'bch'
    symbol = 'BCH'
