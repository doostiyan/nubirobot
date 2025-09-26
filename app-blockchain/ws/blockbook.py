from django.conf import settings

from exchange.base.models import Currencies, get_currency_codename
from exchange.blockchain.api.bsc.bsc_blockbook import BscBlockbookAPI
from exchange.blockchain.api.btc.btc_blockbook import BitcoinBlockbookAPI
from exchange.blockchain.api.doge.doge_blockbook import DogeBlockbookAPI
from exchange.blockchain.api.etc.etc_blockbook import EthereumClassicBlockbookAPI
from exchange.blockchain.api.eth.eth_blockbook import EthereumBlockbookAPI
from exchange.blockchain.contracts_conf import ERC20_contract_info, BEP20_contract_info

from exchange.blockchain.api.bsc.bsc_rpc import BSCRPC
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI
from exchange.blockchain.ws.WSClient import WSClient
from exchange.blockchain.ws.general import GeneralWS


class BlockbookWS(GeneralWS):
    """
    coins:
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer:
    """

    currency: Currencies
    currencies: list

    base_ws_url: str
    PRECISION = 8

    ping_interval = 10
    ping_timeout = 8

    TESTNET_ENABLE = False

    ws = None
    keep_alive_interval = 25
    block_latest_number = 0

    def get_height(self, info, *args, **kwargs):
        data = info.get('data')
        if not data or not isinstance(data, dict):
            return

        height = data.get('height')
        if not height:
            return
        return height

    def run(self):
        host = port = None
        if self.USE_PROXY or settings.NO_INTERNET and not settings.IS_VIP:
            http_proxy = settings.DEFAULT_PROXY
            if http_proxy:
                http_proxy = http_proxy.get('http', 'http://proxy.local:1100')[7:].split(':')
                host = http_proxy[0]
                port = http_proxy[1]

        self.ws = WSClient(
            urls=f'wss://{self.base_ws_url}/websocket',
            reset_cache_key=f'reset_websocket_{get_currency_codename(self.currency)}',
            keep_alive=self.keep_alive_interval,
            on_blocks=self.receive_block
        )
        self.ws.run_forever(http_proxy_host=host, http_proxy_port=port, proxy_type='http', skip_utf8_validation=True)


class EthereumBlockbookWS(BlockbookWS):
    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'
    currency = Currencies.eth
    currencies = [Currencies.eth] + list(ERC20_contract_info[network].keys())
    PRECISION = 18
    base_ws_url = 'ac-dev1.net:39136' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'blockbook-eth.binancechain.io'
    keep_alive_interval = 25
    network_symbol = 'ETH'

    @classmethod
    def addr_block_to_model(cls, address):
        return address.lower()


# Note: Does not work
class BitcoinBlockbookWS(BlockbookWS):
    currency = Currencies.btc
    currencies = [Currencies.btc]
    base_ws_url = 'btc.blockbook.api.phore.io'
    PRECISION = 8
    network_symbol = 'BTC'


# Note: etcblockexplorer.org not available ".com" version is available but its websocket does not work also
class EthereumClassicBlockbookWS(BlockbookWS):
    currency = Currencies.etc
    currencies = [Currencies.etc]
    base_ws_url = 'etcbook.guarda.co'
    PRECISION = 18
    network_symbol = 'ETC'


class DogecoinBlockbookWS(BlockbookWS):
    currency = Currencies.doge
    currencies = [Currencies.doge]
    base_ws_url = 'blockbook-dogecoin.binancechain.io'
    PRECISION = 8
    network_symbol = 'DOGE'


class BinanceSmartChainBlockbookWS(BlockbookWS):
    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'
    currency = Currencies.bnb
    currencies = [Currencies.bnb] + list(BEP20_contract_info[network].keys())
    PRECISION = 18
    USE_PROXY = False
    base_ws_url = 'nodes.nobitex1.ir/bsc-blockbook'
    keep_alive_interval = 25
    network_symbol = 'BSC'
    network_required = True


class BinanceSmartChainKleverBlockbookWS(BlockbookWS):
    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'
    currency = Currencies.bnb
    currencies = [Currencies.bnb] + list(BEP20_contract_info[network].keys())
    PRECISION = 18
    base_ws_url = 'bsc.blockbook.chains.klever.io'
    keep_alive_interval = 1
    network_symbol = 'BSC'
    network_required = True
