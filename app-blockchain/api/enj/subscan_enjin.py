from exchange.blockchain.api.commons.subscan import SubScanApi, SubScanResponseParser, SubScanResponseValidator
from django.conf import settings
from exchange.blockchain.ss58 import ss58_encode
from decimal import Decimal

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class EnjinResponseValidator(SubScanResponseValidator):
    symbol = 'ENJ'
    currency = Currencies.enj
    precision = 18
    min_event_length = 3
    min_valid_tx_amount = Decimal('0.1')


class EnjinResponseParser(SubScanResponseParser):
    validator = EnjinResponseValidator
    symbol = 'ENJ'
    currency = Currencies.enj
    precision = 18

    @classmethod
    def pub_key_to_address(cls, pub_key):
        # SS58 for mainnet is 2135 and for testnet is 9030
        address_format = 2135 if cls.network_mode == 'mainnet' else 9030
        return ss58_encode(pub_key, ss58_format=address_format)


class EnjinSubscanApi(SubScanApi):
    USE_PROXY = True
    parser = EnjinResponseParser
    cache_key = 'enj'
    symbol = 'ENJ'
    _base_url = 'https://enjin.api.subscan.io'
