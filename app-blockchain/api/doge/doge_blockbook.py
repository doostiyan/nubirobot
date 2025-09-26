from decimal import Decimal

from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.blockbook import BlockbookAPI


class DogeBlockbookAPIv2(BlockbookAPI):
    _base_url = 'https://dogebook.guarda.co'
    symbol = 'DOGE'
    currency = Currencies.doge
    cache_key = 'doge'
    min_valid_tx_amount = Decimal('1.00000000')
    last_blocks = 4500
    USE_PROXY = False


class DogeBlockbookAPI(BlockbookAPI):
    # _base_url = 'https://doge.trusteeglobal.com'
    # _base_url = 'https://blockbook-dogecoin.binancechain.io'
    _base_url = 'https://dogeblocks.com'
    # _base_url = 'https://dogecoin.atomicwallet.io'
    # _base_url = 'https://blockbook.doge.zelcore.io'
    symbol = 'DOGE'
    currency = Currencies.doge
    cache_key = 'doge'
    min_valid_tx_amount = Decimal('1.00000000')
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0'
    } if not settings.IS_VIP else {
        'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/109.0'
    }
    last_blocks = 4500
    max_blocks = 20


class DogeNowNodesAPI(BlockbookAPI):
    _base_url = 'https://doge.nownodes.io'
    symbol = 'DOGE'
    api_key_header = {'api-key': f'{settings.NOWNODES_API_KEY}'}
    currency = Currencies.doge
    cache_key = 'doge'
    min_valid_tx_amount = Decimal('1.00000000')
    last_blocks = 4500
