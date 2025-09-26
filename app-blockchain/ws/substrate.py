from django.conf import settings
from exchange.base.models import Currencies
from exchange.blockchain.api.dot.dot_explorer_interface import DotExplorerInterface
from exchange.blockchain.api.dot.subscan import SubscanAPI
from exchange.blockchain.ws.general import GeneralWS


class DotSubstrateWS(GeneralWS):
    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'
    currency = Currencies.dot
    currencies = [Currencies.dot]
    ws_url = 'wss://rpc.polkadot.io'
    # ws_url = 'wss://nodes2.nobitex1.ir/dot-ws/'
    # ws_url = 'wss://1rpc.io/dot'
    testnet_url = 'wss://westend-rpc.polkadot.io'
    USE_PROXY = True
    network_symbol = 'DOT'

    def get_height(self, info, *args, **kwargs):

        data = info.get('header')
        if not data or not isinstance(data, dict):
            return
        height = data.get('number')
        if not height:
            return
        print(height)
        return height

    def run(self):
        from substrateinterface import SubstrateInterface  # pip install substrate-interface
        host = port = None
        if self.USE_PROXY:
            http_proxy = settings.DEFAULT_PROXY
            if http_proxy:
                http_proxy = http_proxy.get('http', 'http://proxy.local:1100')[7:].split(':')
                host = http_proxy[0]
                port = http_proxy[1]
        if self.network == 'testnet':
            substrate = SubstrateInterface(
                url=self.testnet_url,
                ss58_format=42,
                type_registry_preset='westend'
            )
        else:
            print(f'Connect with {host}:{port} proxy')
            try:
                substrate = SubstrateInterface(
                    url=self.ws_url,
                    ss58_format=0,
                    type_registry_preset='polkadot',
                    use_remote_preset=True,
                    ws_options={'http_proxy_host': host, 'http_proxy_port': port},
                )
            except Exception as e:
                print(e)
        substrate.subscribe_block_headers(self.receive_block, finalized_only=True, ignore_decoding_errors=True)
