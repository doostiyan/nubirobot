from exchange.blockchain.api.dydx.dydx_node import DydxPublicRpc, DydxKingnodes, DydxPolkachu, DydxEcostake, DydxEnigma
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface


class DydxExplorerInterface(ExplorerInterface):
    balance_apis = [DydxPolkachu, DydxPublicRpc, DydxKingnodes, DydxEcostake, DydxEnigma]
    tx_details_apis = [DydxPublicRpc, DydxKingnodes, DydxPolkachu, DydxEcostake, DydxEnigma]
    address_txs_apis = [DydxKingnodes, DydxPublicRpc, DydxPolkachu, DydxEcostake, DydxEnigma]
    block_head_apis = [DydxPublicRpc, DydxKingnodes, DydxPolkachu, DydxEcostake, DydxEnigma]
    symbol = 'DYDX'
