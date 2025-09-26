from decimal import Decimal

from django.conf import settings
from exchange.blockchain.api.commons.blockbook import BlockBookApi, BlockBookParser, BlockBookValidator

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class DogeBlockBookParser(BlockBookParser):
    precision = 8
    currency = Currencies.doge
    symbol = 'DOGE'


class DogeBlockBookApi(BlockBookApi):
    parser = DogeBlockBookParser
    symbol = 'DOGE'
    _base_url = 'https://blockbook.doge.zelcore.io'
    # 'https://doge.trusteeglobal.com/'#'https://dogeblocks.com'
    # 'https://blockbook-dogecoin.binancechain.io'
    # 'https://dogecoin.atomicwallet.io'
    cache_key = 'doge'
    GET_BLOCK_ADDRESSES_MAX_NUM = 20
    last_blocks = 4500
    max_workers_for_get_block = 5
    SUPPORT_PAGING = True
    USE_PROXY = True

    @classmethod
    def get_headers(cls):
        return {
            'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/109.0'
        }


class DogeBlockBookApiV2(DogeBlockBookApi):
    instance = None
    _base_url = 'https://dogebook.guarda.co'


class DogeNowNodesApi(DogeBlockBookApi):
    instance = None
    _base_url = 'https://doge.nownodes.io'
    api_key_header = {'api-key': f'{settings.NOWNODES_API_KEY}'}
