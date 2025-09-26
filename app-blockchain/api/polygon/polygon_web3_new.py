from exchange.base.models import Currencies
from exchange.blockchain.contracts_conf import polygon_ERC20_contract_info, polygon_ERC20_contract_currency
from exchange.blockchain.api.commons.web3 import Web3Api, Web3ResponseParser, Web3ResponseValidator


class PolygonWeb3Parser(Web3ResponseParser):
    symbol = 'POL'
    precision = 18
    currency = Currencies.pol

    @classmethod
    def contract_currency_list(cls):
        return polygon_ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return polygon_ERC20_contract_info.get(cls.network_mode)


class PolygonWeb3Api(Web3Api):
    block_height_offset = 5
    parser = PolygonWeb3Parser
    symbol = 'POL'
    cache_key = 'matic'

    # _base_url = 'https://matic-mainnet.chainstacklabs.com'
    # _base_url = 'https://rpc-mainnet.matic.quiknode.pro'
    _base_url = 'https://polygon-pokt.nodies.app'
    # _base_url = 'https://polygon.meowrpc.com'

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
