from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.covalenthq import CovalenthqAPI
from exchange.blockchain.contracts_conf import opera_ftm_contract_currency, opera_ftm_contract_info


class FantomCovalenthqAPI(CovalenthqAPI):

    _base_url = 'https://api.covalenthq.com/v1/250/'
    testnet_url = 'https://api.covalenthq.com/v1/4002/'
    symbol = 'FTM'
    currency = Currencies.ftm
    PRECISION = 18
    cache_key = 'ftm'
    USE_PROXY = True

    @property
    def contract_currency_list(self):
        return opera_ftm_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return opera_ftm_contract_info.get(self.network)
