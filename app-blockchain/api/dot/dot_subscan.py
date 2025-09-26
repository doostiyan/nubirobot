from exchange.blockchain.api.commons.subscan import SubScanApi, SubScanResponseParser, SubScanResponseValidator
from django.conf import settings
from exchange.blockchain.ss58 import ss58_encode

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class DotResponseValidator(SubScanResponseValidator):
    symbol = 'DOT'
    currency = Currencies.dot
    precision = 10
    min_event_length = 3


class DotResponseParser(SubScanResponseParser):
    validator = DotResponseValidator
    symbol = 'DOT'
    currency = Currencies.dot
    precision = 10

    @classmethod
    def pub_key_to_address(cls, pub_key):
        # SS58 for mainnet is 2135 and for testnet is 9030
        address_format = 0 if cls.network_mode == 'mainnet' else 42
        return ss58_encode(pub_key, ss58_format=address_format)


class DotSubscanApi(SubScanApi):
    USE_PROXY = True
    parser = DotResponseParser
    cache_key = 'dot'
    symbol = 'DOT'
    _base_url = 'https://polkadot.api.subscan.io'
    testnet_url = 'https://westend.api.subscan.io/'
    block_height_offset = 5
