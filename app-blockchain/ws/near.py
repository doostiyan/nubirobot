
from django.conf import settings

from exchange.blockchain.api.near.near_explorer_interface import RpcNearExplorerInterface
from exchange.blockchain.api.near.near_nearscan import NearScan

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies, get_currency_codename
else:
    from exchange.base.models import get_currency_codename, Currencies
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI
from exchange.blockchain.ws.general import GeneralWS
from exchange.blockchain.ws.WSClient import NearWSClient


class NearWS(GeneralWS):

    ws_url = 'wss://explorer-backend-mainnet-prod-24ktefolwq-uc.a.run.app/ws'
    # ws_url = 'wss://backend-mainnet-1713.onrender.com/ws'

    currency = Currencies.near
    currencies = [Currencies.near]
    network_symbol = 'NEAR'
    PRECISION = 18
    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'

    ws = None
    blockchain_ws = None
    keep_alive_interval = 25
    block_latest_number = 0
    USE_PROXY = True

    def get_height(self, info, *args, **kwargs):
        data = info.get('result').get('data')
        if not data or not isinstance(data, dict):
            return
        return data.get('height')

    def run(self):
        host = port = None
        if self.USE_PROXY:
            http_proxy = settings.DEFAULT_PROXY
            if http_proxy:
                http_proxy = http_proxy.get('http', 'http://proxy.local:1100')[7:].split(':')
                host = http_proxy[0]
                port = http_proxy[1]
            print(http_proxy)

        self.ws = NearWSClient(
            urls=f'{self.ws_url}',
            reset_cache_key=f'reset_geth_websocket_{get_currency_codename(self.currency)}',
            keep_alive=self.keep_alive_interval,
        )
        self.ws.on_blocks += self.receive_block
        self.ws.run_forever(http_proxy_host=host, http_proxy_port=port, skip_utf8_validation=True)

