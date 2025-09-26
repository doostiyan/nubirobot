from decimal import Decimal

from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.blockbook import BlockbookAPI


class LitecoinBlockbookAPI(BlockbookAPI):
    # _base_url = 'http://68.183.219.13/'
    _base_url = 'https://blockbook.ltc.zelcore.io'
    symbol = 'LTC'
    PRECISION = 8
    currency = Currencies.ltc
    cache_key = 'ltc'
    ignore_warning = False
    USE_PROXY = True if not settings.IS_VIP else False
    last_blocks = 2000
    max_blocks = 10
    min_valid_tx_amount = Decimal('0.0005 ')


class LitecoinBinanceBlockbookAPI(BlockbookAPI):
    _base_url = 'https://blockbook-litecoin.binancechain.io/'
    symbol = 'LTC'
    PRECISION = 8
    currency = Currencies.ltc
    cache_key = 'ltc'
    ignore_warning = True
    last_blocks = 800
    max_blocks = 10
    min_valid_tx_amount = Decimal('0.0005 ')


class LitecoinAtomicWalletBlockbookAPI(BlockbookAPI):
    _base_url = 'https://litecoin.atomicwallet.io/'
    symbol = 'LTC'
    PRECISION = 8
    currency = Currencies.ltc
    cache_key = 'ltc'
    ignore_warning = True
    last_blocks = 800
    max_blocks = 10
    min_valid_tx_amount = Decimal('0.0005 ')


class LitecoinHeatWalletBlockbookAPI(BlockbookAPI):
    _base_url = 'https://ltc1.heatwallet.com/'
    symbol = 'LTC'
    PRECISION = 8
    currency = Currencies.ltc
    cache_key = 'ltc'
    ignore_warning = True
    last_blocks = 800
    max_blocks = 10
    min_valid_tx_amount = Decimal('0.0005 ')
