from cashaddress.convert import InvalidAddress
from cashaddress import convert
from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.commons.blockbook import BlockBookParser, BlockBookApi


class BitcoinCashBlockBookParser(BlockBookParser):
    precision = 8
    symbol = 'BCH'
    currency = Currencies.bch

    @classmethod
    def convert_address(cls, address):
        try:
            return convert.to_legacy_address(address)
        except InvalidAddress:
            return None


class BitcoinCashBlockBookApi(BlockBookApi):
    parser = BitcoinCashBlockBookParser
    # _base_url = 'https://bchblockexplorer.com'
    # _base_url = 'https://bch.trusteeglobal.com/'
    _base_url = 'https://bitcoin-cash-node.atomicwallet.io'
    symbol = 'BCH'
    cache_key = 'bch'
    GET_BLOCK_ADDRESSES_MAX_NUM = 5
    USE_PROXY = True
    SUPPORT_PAGING = True
    max_workers_for_get_block = 5

    @classmethod
    def get_headers(cls):
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0'
        } if not settings.IS_VIP else {
            'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/109.0'
        }
        return headers
