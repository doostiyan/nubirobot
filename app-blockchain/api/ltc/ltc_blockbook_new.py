from decimal import Decimal
from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.commons.blockbook import BlockBookParser, BlockBookApi


class LiteCoinBlockBookParser(BlockBookParser):
    precision = 8
    symbol = 'LTC'
    currency = Currencies.ltc


class LiteCoinBlockBookAPI(BlockBookApi):
    # _base_url = 'http://68.183.219.13/'
    _base_url = 'https://blockbook.ltc.zelcore.io'
    parser = LiteCoinBlockBookParser
    symbol = 'LTC'
    currency = Currencies.ltc
    cache_key = 'ltc'
    ignore_warning = False
    USE_PROXY = True if not settings.IS_VIP else False
    last_blocks = 2000
    GET_BLOCK_ADDRESSES_MAX_NUM = 10
    SUPPORT_PAGING = True
    max_workers_for_get_block = 5
    min_valid_tx_amount = Decimal('0.0005')
    instance = None


class LiteCoinBinanceBlockBookAPI(LiteCoinBlockBookAPI):
    _base_url = 'https://blockbook-litecoin.binancechain.io/'
    ignore_warning = True
    last_blocks = 800
    instance = None


class LiteCoinAtomicWalletBlockBookAPI(LiteCoinBlockBookAPI):
    _base_url = 'https://litecoin.atomicwallet.io/'
    ignore_warning = True
    last_blocks = 800
    instance = None


class LiteCoinHeatWalletBlockbookAPI(LiteCoinBlockBookAPI):
    _base_url = 'https://ltc1.heatwallet.com/'
    ignore_warning = True
    last_blocks = 800
    instance = None
