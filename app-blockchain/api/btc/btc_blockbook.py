from decimal import Decimal

from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.blockbook import BlockbookAPI


class BitcoinBlockbookAPI(BlockbookAPI):

    # _base_url = 'https://blockbook.btc.zelcore.io'
    # _base_url = 'https://btc.alaio.io'
    # _base_url = 'http://167.172.107.122'
    # _base_url = 'https://bitcoinblockexplorers.com/'
    # _base_url = 'https://btc.trusteeglobal.com/'
    _base_url = 'https://btc.exan.tech/'

    symbol = 'BTC'
    PRECISION = 8
    currency = Currencies.btc
    cache_key = 'btc'
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0'
    } if not settings.IS_VIP else {
        'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/109.0'
    }
    last_blocks = 3000
    max_blocks = 2
    # USE_PROXY = True
    min_valid_tx_amount = Decimal('0.0005')
