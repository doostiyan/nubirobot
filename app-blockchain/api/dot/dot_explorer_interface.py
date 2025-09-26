from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.dot.dot_subscan import DotSubscanApi
from .dot_polaris import DotPolarisApi


class DotExplorerInterface(ExplorerInterface):
    balance_apis = [DotSubscanApi]
    tx_details_apis = [DotSubscanApi, DotPolarisApi]
    block_txs_apis = [DotPolarisApi, DotSubscanApi]
    address_txs_apis = [DotSubscanApi, DotPolarisApi]
    block_head_apis = [DotPolarisApi, DotSubscanApi]
    symbol = 'DOT'
