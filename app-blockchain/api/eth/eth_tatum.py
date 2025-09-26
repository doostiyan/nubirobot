from django.conf import settings
from exchange.blockchain.api.commons.eth_like_tatum import EthLikeTatumApi, EthLikeTatumResponseValidator, \
    EthLikeTatumResponseParser
from exchange.blockchain.contracts_conf import ERC20_contract_info, ERC20_contract_currency

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class ETHTatumResponseParser(EthLikeTatumResponseParser):
    validator = EthLikeTatumResponseValidator
    symbol = 'ETH'
    precision = 18
    currency = Currencies.eth

    @classmethod
    def contract_currency_list(cls):
        return ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return ERC20_contract_info.get(cls.network_mode)


class ETHTatumApi(EthLikeTatumApi):
    symbol = 'ETH'
    cache_key = 'eth'
    currency = Currencies.eth
    parser = ETHTatumResponseParser
    _base_url = 'https://api.tatum.io/v3/ethereum/'
