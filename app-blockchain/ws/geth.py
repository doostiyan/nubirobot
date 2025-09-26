import random

from django.conf import settings

from exchange.base.models import Currencies, get_currency_codename
from exchange.blockchain.api.avax.avalanche_web3 import AvalancheWeb3API
from exchange.blockchain.api.etc.etc_blockbook import EthereumClassicBlockbookAPI
from exchange.blockchain.api.eth.eth_blockbook import EthereumBlockbookAPI
from exchange.blockchain.api.bsc.bsc_rpc import BSCRPC
from exchange.blockchain.api.eth.eth_web3 import ETHWeb3
from exchange.blockchain.api.ftm.ftm_web3 import FtmWeb3API
from exchange.blockchain.api.ftm.ftm_graphql import FantomGraphQlAPI
from exchange.blockchain.api.one.one_rpc import HarmonyRPC
from exchange.blockchain.api.polygon.polygon_web3 import PolygonWeb3API
from exchange.blockchain.contracts_conf import (
    ERC20_contract_info, BEP20_contract_info, opera_ftm_contract_info,
    polygon_ERC20_contract_info, avalanche_ERC20_contract_info, harmony_ERC20_contract_info
)
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI
from exchange.blockchain.ws.general import GeneralWS
from exchange.blockchain.ws.WSClient import GethWSClient


class GethWS(GeneralWS):
    """
    coins:
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer:
    """

    currency = Currencies.eth
    currencies = [Currencies.eth, Currencies.usdt]

    ws_url = settings.GETH_WS_URL

    PRECISION = 18
    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'

    ws = None
    blockchain_ws = None
    keep_alive_interval = 25
    block_latest_number = 2

    def get_height(self, info, subscription_id=None,  update_nr=None):
        data = info.get('params').get('result')
        if not data or not isinstance(data, dict):
            return
        height = data.get('number')
        if not height:
            return
        height = int(height, 16)
        return height

    def run(self):
        host = port = None
        if self.USE_PROXY:
            http_proxy = settings.DEFAULT_PROXY
            if http_proxy:
                http_proxy = http_proxy.get('http', 'http://proxy.local:1100')[7:].split(':')
                host = http_proxy[0]
                port = http_proxy[1]

        self.ws = GethWSClient(
            urls=f'{self.ws_url}',
            reset_cache_key=f'reset_geth_websocket_{get_currency_codename(self.currency)}',
            keep_alive=self.keep_alive_interval,
        )
        self.ws.on_blocks += self.receive_block
        self.ws.run_forever(http_proxy_host=host, http_proxy_port=port, skip_utf8_validation=True)


class EthGethWS(GethWS):
    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'
    currency = Currencies.eth
    currencies = [Currencies.eth] + list(ERC20_contract_info[network].keys())
    keep_alive_interval = 10
    network_symbol = 'ETH'


class EthWeb3WS(GethWS):
    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'
    currency = Currencies.eth
    currencies = [Currencies.eth] + list(ERC20_contract_info[network].keys())
    # ws_url = f'wss://mainnet.infura.io/ws/v3/{random.choice(settings.WS_INFURA_PROJECT_ID)}'
    ws_url = 'wss://ethereum-rpc.publicnode.com'
    # ws_url = 'wss://eth.drpc.org'
    network_symbol = 'ETH'
    # USE_PROXY = True


class EtcRiverWS(GethWS):
    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'
    currency = Currencies.etc
    currencies = [Currencies.etc]
    API_KEY = '39026656a97d41dcbf6c3ac89dbe54b3' if not settings.IS_VIP else '37e4e2b5ca3a44b6974eaabb9cb1a08b'
    ws_url = f'wss://{API_KEY}.etc.ws.rivet.cloud/'
    network_symbol = 'ETC'


class BscGethWS(GethWS):
    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'
    currency = Currencies.bnb
    currencies = [Currencies.bnb] + list(BEP20_contract_info[network].keys())
    ws_url = 'wss://rpc-bsc.48.club/ws/'
    # ws_url = 'wss://icy-long-dust.bsc.discover.quiknode.pro/79814e7de17bc210711645e3ba7c4c954a972b96'
    # ws_url = 'wss://nodes3.nobitex1.ir/bsc-fullnode-ws/'
    # ws_url = 'wss://bsc-mainnet.public.blastapi.io'
    # ws_url = 'wss://bsc.blockpi.network/v1/ws/4c3b520c559d865de1f75a3df80ddb83fa13023e'
    # ws_url = 'wss://bsc-rpc.publicnode.com'
    USE_PROXY = False

    network_symbol = 'BSC'
    network_required = True
    block_latest_number = 20


class BscWeb3WS(GethWS):
    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'
    currency = Currencies.bnb
    currencies = [Currencies.bnb] + list(BEP20_contract_info[network].keys())
    ws_url = f'wss://speedy-nodes-nyc.moralis.io/5c09e60076244e266f6ca740/bsc/{network}/ws'

    network_symbol = 'BSC'
    network_required = True
    block_latest_number = 20


class FtmWeb3WS(GethWS):
    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'
    currency = Currencies.ftm
    currencies = [Currencies.ftm] + list(opera_ftm_contract_info[network].keys())
    # ws_url = 'wss://wsapi.fantom.network'
    # ws_url = 'wss://fantom-mainnet.public.blastapi.io'
    ws_url = 'wss://fantom-rpc.publicnode.com'
    # ws_url = 'wss://fantom.drpc.org'

    network_symbol = 'FTM'
    block_latest_number = 12
    USE_PROXY = False


class PolygonWeb3WS(GethWS):
    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'
    currency = Currencies.pol
    currencies = [Currencies.pol] + list(polygon_ERC20_contract_info[network].keys())
    # ws_url = 'wss://boldest-cosmopolitan-orb.matic.discover.quiknode.pro/93d2cc7aacd65c87428d812ef8d6b53f942d9df6/'
    # ws_url = 'wss://polygon.drpc.org'
    ws_url = 'wss://polygon-bor-rpc.publicnode.com'

    network_symbol = 'MATIC'
    block_latest_number = 25
    USE_PROXY = False


class AvalancheWeb3WS(GethWS):
    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'
    currency = Currencies.avax
    currencies = [Currencies.avax] + list(avalanche_ERC20_contract_info[network].keys())
    ws_url = 'wss://api.avax.network/ext/bc/C/ws'
    # ws_url = 'wss://avalanche.blockpi.network/v1/ws/012853e963c7376648bfb61c588793dc4d3c65fd'

    network_symbol = 'AVAX'
    block_latest_number = 12
    USE_PROXY = False

    # @property
    # def ws_url(self):
    #     return f'wss://avax.getblock.io/mainnet/ext/bc/C/ws?api_key={random.choice(settings.AVAX_GET_BLOCK_API_KEY)}'


class HarmonyWeb3WS(GethWS):
    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'
    currency = Currencies.one
    currencies = [Currencies.one] + list(harmony_ERC20_contract_info[network].keys())
    ws_url = 'wss://ws.s0.t.hmny.io/'  # or wss://ws-harmony-mainnet.chainstacklabs.com/

    network_symbol = 'ONE'
    block_latest_number = 12
    USE_PROXY = False
