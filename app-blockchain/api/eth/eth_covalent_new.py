from exchange.base.models import Currencies
from exchange.blockchain.api.commons.covalenthq import CovalenthqApi, CovalenthqResponseParser
from exchange.blockchain.contracts_conf import ERC20_contract_info, ERC20_contract_currency


class ETHCovalenthqResponseParser(CovalenthqResponseParser):
    symbol = 'ETH'
    currency = Currencies.eth
    precision = 18

    @classmethod
    def contract_currency_list(cls):
        return ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return ERC20_contract_info.get(cls.network_mode)


class ETHCovalenthqApi(CovalenthqApi):
    parser = ETHCovalenthqResponseParser
    cache_key = 'eth'
    USE_PROXY = True

    _base_url = 'https://api.covalenthq.com/v1/1'
    testnet_url = 'https://api.covalenthq.com/v1/1'
