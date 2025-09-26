from decimal import Decimal
from django.conf import settings
from exchange.base.models import Currencies
from exchange.blockchain.api.commons.blockbook import BlockBookApi, BlockBookParser, BlockBookValidator


class BitcoinBlockBookValidator(BlockBookValidator):
    min_valid_tx_amount = Decimal('0.0005')


class BitcoinBlockBookParser(BlockBookParser):
    validator = BitcoinBlockBookValidator
    precision = 8
    symbol = 'BTC'
    currency = Currencies.btc


class BitcoinBlockBookAPI(BlockBookApi):
    parser = BitcoinBlockBookParser
    symbol = 'BTC'
    cache_key = 'btc'
    last_blocks = 3000
    GET_BLOCK_ADDRESSES_MAX_NUM = 2
    max_workers_for_get_block = 5
    SUPPORT_PAGING = True
    # _base_url = 'https://btc.exan.tech/'
    _base_url = 'https://blockbook.btc.zelcore.io'
    # _base_url = 'https://btc.alaio.io'
    # _base_url = 'http://167.172.107.122'
    # _base_url = 'https://bitcoinblockexplorers.com/'
    # _base_url = 'https://btc.trusteeglobal.com/'

    @classmethod
    def get_headers(cls):
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0'
        } if not settings.IS_VIP else {
            'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/109.0'
        }
        return headers
