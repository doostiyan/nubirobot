from decimal import Decimal
from django.conf import settings
from exchange.blockchain.api.commons.btc_like_tatum import BtcLikeTatumApi, TatumResponseParser, TatumResponseValidator

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class LiteCoinTatumResponseValidator(TatumResponseValidator):
    min_valid_tx_amount = Decimal('0.0005')


class LiteCoinTatumResponseParser(TatumResponseParser):
    validator = LiteCoinTatumResponseValidator
    symbol = 'LTC'
    currency = Currencies.ltc


class LiteCoinTatumApi(BtcLikeTatumApi):
    symbol = 'LTC'
    cache_key = 'ltc'
    currency = Currencies.ltc
    parser = LiteCoinTatumResponseParser
    _base_url = 'https://api.tatum.io/v3/litecoin/'
    instance = None