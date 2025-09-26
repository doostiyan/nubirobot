import random
from typing import Optional

from django.conf import settings

from exchange.blockchain.api.commons.eth_like_tatum import (
    EthLikeTatumApi,
    EthLikeTatumResponseParser,
    EthLikeTatumResponseValidator,
)
from exchange.blockchain.contracts_conf import BASE_ERC20_contract_currency, BASE_ERC20_contract_info

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class BaseTatumResponseParser(EthLikeTatumResponseParser):
    validator = EthLikeTatumResponseValidator
    symbol = 'ETH'
    precision = 18
    currency = Currencies.eth

    @classmethod
    def contract_currency_list(cls) -> dict:
        return BASE_ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls) -> dict:
        return BASE_ERC20_contract_info.get(cls.network_mode)


class BaseTatumApi(EthLikeTatumApi):
    symbol = 'ETH'
    cache_key = 'base'
    currency = Currencies.eth
    parser = BaseTatumResponseParser
    _base_url = 'https://api.tatum.io/v3/base/'
    instance = None

    @classmethod
    def get_api_key(cls) -> Optional[str]:
        return random.choice(settings.BASE_TATUM_API_KEYS)
