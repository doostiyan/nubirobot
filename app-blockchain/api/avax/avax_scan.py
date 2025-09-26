import random
from typing import Optional

from django.conf import settings

from exchange.blockchain.contracts_conf import avalanche_ERC20_contract_currency, avalanche_ERC20_contract_info

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
from exchange.blockchain.api.commons.blockscan import BlockScanAPI, BlockScanResponseParser


class AvaxResponseResponseParser(BlockScanResponseParser):
    symbol = 'AVAX'
    precision = 18
    currency = Currencies.avax

    @classmethod
    def contract_info_list(cls) -> dict:
        return avalanche_ERC20_contract_info.get(cls.network_mode)

    @classmethod
    def contract_currency_list(cls) -> dict:
        return avalanche_ERC20_contract_currency.get(cls.network_mode)


class AvaxScanApi(BlockScanAPI):
    """

    """
    parser = AvaxResponseResponseParser
    symbol = 'AVAX'
    cache_key = 'avax'
    rate_limit = 0.2
    chain_id = 43114

    @classmethod
    def get_api_key(cls) -> Optional[str]:
        return random.choice(settings.AVALANCHE_SCAN_API_KEY)
