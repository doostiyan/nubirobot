from exchange.base.models import Currencies
from exchange.blockchain.ws.geth import (
    EtcRiverWS, BscGethWS, BscWeb3WS, FtmWeb3WS, PolygonWeb3WS, HarmonyWeb3WS, AvalancheWeb3WS, EthWeb3WS
)
from exchange.blockchain.ws.lnd import LndWS
from exchange.blockchain.ws.substrate import DotSubstrateWS

WEBSOCKET_CLASS = {
    # Currencies.eth: EthereumBlockbookWS,
    Currencies.bnb: BscGethWS,
    Currencies.eth: EthWeb3WS,
    Currencies.etc: EtcRiverWS,
    Currencies.btc: {
        'BTCLN': LndWS,
    },
    Currencies.dot: DotSubstrateWS,
    Currencies.ftm: FtmWeb3WS,
    Currencies.pol: PolygonWeb3WS,
    Currencies.avax: AvalancheWeb3WS,
    Currencies.one: HarmonyWeb3WS,
}


def run_websocket(currency=None, network=None):
    """Process all withdraw automatically.
    Only process once. If fails does not retry automatically.
    """
    if currency is None:
        currency = Currencies.eth
    websocket_class = WEBSOCKET_CLASS.get(currency)
    if network is not None:
        websocket_class = websocket_class.get(network)
    if websocket_class is None:
        print(f'[Error] Currency not available in websocket class: {currency}')
        return
    print('============================')
    print('New round started...........')
    print('============================')
    websocket_class().run()
