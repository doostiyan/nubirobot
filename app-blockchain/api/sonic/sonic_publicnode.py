from exchange.blockchain.api.commons.web3 import Web3Api, Web3ResponseParser
from exchange.blockchain.models import Currencies


class SonicPublicNodeWeb3Parser(Web3ResponseParser):
    symbol = 'S'
    currency = Currencies.s


class SonicPublicNodeWeb3API(Web3Api):
    parser = SonicPublicNodeWeb3Parser
    symbol = 'S'
    cache_key = 'sonic'
    _base_url = 'https://sonic.drpc.org'
    # https://rpc.ankr.com/sonic_mainnet
    # https://1rpc.io/sonic
    # https://rpc.soniclabs.com
    # https://sonic-blaze-rpc.publicnode.com

    USE_PROXY = True

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
