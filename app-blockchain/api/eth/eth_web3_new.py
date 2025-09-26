from exchange.base.models import Currencies
from exchange.blockchain.api.commons.web3 import Web3Api, Web3ResponseParser, Web3ResponseValidator
from exchange.blockchain.contracts_conf import ERC20_contract_info, ERC20_contract_currency


class ETHWeb3ResponseParser(Web3ResponseParser):
    validator = Web3ResponseValidator
    symbol = 'ETH'
    currency = Currencies.eth
    precision = 18

    @classmethod
    def contract_currency_list(cls):
        return ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return ERC20_contract_info.get(cls.network_mode)


class ETHWeb3Api(Web3Api):
    parser = ETHWeb3ResponseParser
    rate_limit = 0
    cache_key = 'eth'

    # _base_url = 'https://mainnet.infura.io/v3/' + random.choice(settings.WEB3_API_INFURA_PROJECT_ID)
    _base_url = 'https://ethereum.publicnode.com'

