import random

from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.web3 import Web3API
from exchange.blockchain.contracts_conf import ERC20_contract_info, ERC20_contract_currency


class ETHWeb3(Web3API):

    active = True
    TOKEN_NETWORK = True
    symbol = 'ETH'
    currency = Currencies.eth
    rate_limit = 0
    PRECISION = 18
    cache_key = 'eth'

    # _base_url = 'https://mainnet.infura.io/v3/' + random.choice(settings.WEB3_API_INFURA_PROJECT_ID)
    _base_url = 'https://ethereum.publicnode.com'

    @property
    def contract_currency_list(self):
        return ERC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return ERC20_contract_info.get(self.network)
