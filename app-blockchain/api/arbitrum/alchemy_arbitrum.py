from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.commons.web3 import Web3ResponseParser, Web3Api, Web3ResponseValidator
from exchange.blockchain.contracts_conf import arbitrum_ERC20_contract_currency, arbitrum_ERC20_contract_info


class AlchemyArbitrumResponseParser(Web3ResponseParser):
    validator = Web3ResponseValidator

    symbol = 'ETH'
    currency = Currencies.eth
    precision = 18

    @classmethod
    def contract_currency_list(cls):
        return arbitrum_ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return arbitrum_ERC20_contract_info.get(cls.network_mode)


class AlchemyArbitrumApi(Web3Api):
    parser = AlchemyArbitrumResponseParser
    #_base_url = 'https://arb-mainnet.g.alchemy.com/v2/Z9badAriDKKohfGZjIMhaujcpLQiRd74'
    # _base_url = 'https://arbitrum.meowrpc.com'
    #_base_url = 'https://arbitrum-one.publicnode.com'
    # _base_url = 'https://arbitrum.llamarpc.com'
    _base_url = 'https://arb1.arbitrum.io/rpc'
    cache_key = 'arb'
    GET_BLOCK_ADDRESSES_MAX_NUM = 500
    max_workers_for_get_block = 3
    block_height_offset = 10
    instance = None
    USE_PROXY = True
