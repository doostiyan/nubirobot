from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.covalenthq import CovalenthqAPI
from exchange.blockchain.contracts_conf import avalanche_ERC20_contract_info, avalanche_ERC20_contract_currency


class AvalancheCovalenthqAPI(CovalenthqAPI):

    _base_url = 'https://api.covalenthq.com/v1/43114/'
    testnet_url = 'https://api.covalenthq.com/v1/43113/'
    symbol = 'AVAX'
    currency = Currencies.avax
    PRECISION = 18
    cache_key = 'avax'

    @property
    def contract_currency_list(self):
        return avalanche_ERC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return avalanche_ERC20_contract_info.get(self.network)
