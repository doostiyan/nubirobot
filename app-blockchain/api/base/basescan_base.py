import random
from typing import Optional

from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.commons.blockscan import BlockScanAPI, BlockScanResponseParser
from exchange.blockchain.contracts_conf import BASE_ERC20_contract_currency, BASE_ERC20_contract_info


class BaseScanResponseParser(BlockScanResponseParser):
    symbol = 'ETH'
    currency = Currencies.eth
    decimals = 18

    @classmethod
    def contract_currency_list(cls) -> dict:
        return BASE_ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls) -> dict:
        return BASE_ERC20_contract_info.get(cls.network_mode)


class BaseScanAPI(BlockScanAPI):
    parser = BaseScanResponseParser
    instance = None
    symbol = 'ETH'
    cache_key = 'base'
    chain_id = 8453

    @classmethod
    def get_api_key(cls) -> Optional[str]:
        return random.choice(settings.BASESCAN_API_KEYS)
