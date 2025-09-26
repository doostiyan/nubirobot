import random

from django.conf import settings
from exchange.blockchain.api.commons.blockscan import BlockScanAPI, BlockScanResponseParser
from exchange.blockchain.models import Currencies


class SonicScanParser(BlockScanResponseParser):
    symbol: str = 'S'
    currency = Currencies.s


class SonicScanApi(BlockScanAPI):
    parser = SonicScanParser
    need_transaction_receipt = True

    testnet_url: str = 'https://api-testnet.sonicscan.org'
    symbol: str = 'S'
    cache_key: str = 'sonic'
    chain_id = 146

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.SONIC_SONICSCAN_APIKEY)
