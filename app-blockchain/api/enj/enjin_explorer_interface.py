from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.enj.subscan_enjin import EnjinSubscanApi


class EnjinExplorerInterface(ExplorerInterface):
    balance_apis = [EnjinSubscanApi]
    tx_details_apis = [EnjinSubscanApi]
    block_txs_apis = [EnjinSubscanApi]
    address_txs_apis = [EnjinSubscanApi]
    block_head_apis = [EnjinSubscanApi]
    symbol = 'ENJ'
