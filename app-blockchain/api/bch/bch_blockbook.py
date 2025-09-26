from decimal import Decimal

from cashaddress import convert
from cashaddress.convert import InvalidAddress
from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.blockbook import BlockbookAPI


class BitcoinCashBlockbookAPI(BlockbookAPI):

    # _base_url = 'https://bchblockexplorer.com'
    # _base_url = 'https://bitcoin-cash-node.atomicwallet.io'
    _base_url = 'https://bch.trusteeglobal.com/'
    symbol = 'BCH'
    PRECISION = 8
    currency = Currencies.bch
    cache_key = 'bch'
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0'
    } if not settings.IS_VIP else {
        'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/109.0'
    }

    max_blocks = 2

    USE_PROXY = True
    min_valid_tx_amount = Decimal('0.003')

    @classmethod
    def convert_address(cls, address):
        try:
            return convert.to_legacy_address(address)
        except InvalidAddress:
            return None
