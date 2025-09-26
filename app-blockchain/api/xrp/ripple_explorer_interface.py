from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from .new_xrp_rpc import RippleClusterApi, RippleWsApi, RippleS1Api, RippleS2Api


class RippleExplorerInterface(ExplorerInterface):
    balance_apis = [RippleS2Api, RippleClusterApi, RippleWsApi, RippleS1Api]
    tx_details_apis = [RippleS1Api, RippleClusterApi, RippleWsApi, RippleS1Api, RippleS2Api]
    block_txs_apis = []
    address_txs_apis = [RippleWsApi, RippleS1Api, RippleClusterApi, RippleS2Api]
    block_head_apis = []
    symbol = 'XRP'
