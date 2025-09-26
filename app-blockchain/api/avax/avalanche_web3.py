from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.web3 import Web3API
from exchange.blockchain.contracts_conf import avalanche_ERC20_contract_info, avalanche_ERC20_contract_currency


class AvalancheWeb3API(Web3API):
    """
    Avalanche Web3 API.

    supported coins: Avax

    API docs: https://web3py.readthedocs.io/'

    supported requests:
        get_balance
        check_block_status
        get_latest_block
    """

    symbol = 'AVAX'
    currency = Currencies.avax
    cache_key = 'avax'
    block_height_offset = 12
    _base_url = 'https://avalanche-c-chain-rpc.publicnode.com'

    def __init__(self):
        from web3.middleware import ExtraDataToPOAMiddleware
        super().__init__()
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    @property
    def contract_currency_list(self):
        return avalanche_ERC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return avalanche_ERC20_contract_info.get(self.network)
