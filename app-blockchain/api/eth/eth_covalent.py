from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.covalenthq import CovalenthqAPI
from exchange.blockchain.contracts_conf import ERC20_contract_info, ERC20_contract_currency


class ETHCovalenthqAPI(CovalenthqAPI):

    _base_url = 'https://api.covalenthq.com/v1/1/'
    testnet_url = 'https://api.covalenthq.com/v1/1/'
    symbol = 'ETH'
    currency = Currencies.eth
    PRECISION = 18
    cache_key = 'eth'
    # USE_PROXY = True

    @property
    def contract_currency_list(self):
        return ERC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return ERC20_contract_info.get(self.network)
