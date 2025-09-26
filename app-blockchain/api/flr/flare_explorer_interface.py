from exchange.blockchain.api.flr.flare_ankr import FlareAnkrApi
from exchange.blockchain.api.flr.flare_explorer import FlareExplorerApi
from exchange.blockchain.api.flr.flare_routescan import FlareRoutescanApi
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface


class FlareExplorerInterface(ExplorerInterface):
    balance_apis = [FlareExplorerApi]
    tx_details_apis = [FlareAnkrApi, FlareExplorerApi, FlareRoutescanApi]
    address_txs_apis = [FlareExplorerApi, FlareRoutescanApi]
    block_txs_apis = [FlareExplorerApi, FlareAnkrApi, FlareRoutescanApi]
    block_head_apis = [FlareExplorerApi, FlareAnkrApi, FlareRoutescanApi]
    symbol = 'FLR'
