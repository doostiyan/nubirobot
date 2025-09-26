from django.conf import settings

from exchange.base.models import Currencies, get_currency_codename
from exchange.blockchain.api.avax.avalanche_web3 import AvalancheWeb3API
from exchange.blockchain.contracts_conf import avalanche_ERC20_contract_info
from exchange.blockchain.ws.WSClient import AvaxWSClient
from exchange.blockchain.ws.general import GeneralWS


class AvaxWS(GeneralWS):
    """
    coins:
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer:
    """

    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'
    currency = Currencies.avax
    currencies = [Currencies.avax] + list(avalanche_ERC20_contract_info[network].keys())
    ws_url = 'wss://snowtrace.io/wshandler'
    inspector = AvalancheWeb3API
    network_symbol = 'AVAX'
    block_latest_number = 12
    USE_PROXY = True

    def get_height(self, info, subscription_id=None,  update_nr=None):
        data = info.get('dashb').get('lastblock')
        if not data:
            return
        height = int(data)
        if not height:
            return
        return height

    def run(self):
        host = port = None
        if self.USE_PROXY:
            http_proxy = settings.DEFAULT_PROXY
            if http_proxy:
                http_proxy = http_proxy.get('http', 'http://proxy.local:1100')[7:].split(':')
                host = http_proxy[0]
                port = http_proxy[1]

        self.ws = AvaxWSClient(
            urls=f'{self.ws_url}',
            reset_cache_key=f'reset_geth_websocket_{get_currency_codename(self.currency)}',
            keep_alive=self.keep_alive_interval,
        )
        self.ws.on_blocks += self.receive_block
        self.ws.run_forever(http_proxy_host=host, http_proxy_port=port, skip_utf8_validation=True)
