from exchange.base.models import Currencies
from exchange.blockchain.api.commons.web3 import Web3Api, Web3ResponseParser
from exchange.blockchain.contracts_conf import avalanche_ERC20_contract_info, avalanche_ERC20_contract_currency


class AvalancheWeb3Parser(Web3ResponseParser):
    symbol = 'AVAX'
    currency = Currencies.avax

    @classmethod
    def contract_currency_list(cls):
        return avalanche_ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return avalanche_ERC20_contract_info.get(cls.network_mode)


class AvalancheWeb3API(Web3Api):
    parser = AvalancheWeb3Parser
    instance = None
    symbol = 'AVAX'
    cache_key = 'avax'
    _base_url = 'https://avalanche.drpc.org'

    # https://avalanche.rpc.thirdweb.com
    # https://avalanche-evm.publicnode.com
    # 'https://api.avax.network/ext/bc/C/rpc'

    def __init__(self):
        import asyncio
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())
        """
         The code above checks if an event loop exists, if not, create one. This is needed when code runs in a thread 
         other than main thread(e.g. UpdateBlockHeadDiffCron in this project) because python does not create an event
         loop for it automatically.
        """
        from web3.middleware import ExtraDataToPOAMiddleware
        super().__init__()
        self.web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
