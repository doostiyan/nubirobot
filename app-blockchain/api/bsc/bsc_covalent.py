from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.covalenthq import CovalenthqAPI
from exchange.blockchain.contracts_conf import BEP20_contract_currency, BEP20_contract_info


class BSCCovalenthqAPI(CovalenthqAPI):

    _base_url = 'https://api.covalenthq.com/v1/bsc-mainnet/'
    testnet_url = 'https://api.covalenthq.com/v1/97/'
    symbol = 'BNB'
    currency = Currencies.bnb
    PRECISION = 18
    cache_key = 'bsc'

    @property
    def contract_currency_list(self):
        return BEP20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return BEP20_contract_info.get(self.network)
