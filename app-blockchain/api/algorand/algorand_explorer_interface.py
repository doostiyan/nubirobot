from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.algorand.algorand_algonode import (AlgoNodeAlgorandApi, BlockDaemonAlgorandApi,
                                                                NodeRealAlgorandApi)
from exchange.blockchain.api.algorand.algorand_bloq_cloud import BloqCloudAlgorandApi
from exchange.blockchain.api.algorand.algorand_tatum import TatumAlgorandApi


class AlgorandExplorerInterface(ExplorerInterface):
    balance_apis = [AlgoNodeAlgorandApi, BlockDaemonAlgorandApi, NodeRealAlgorandApi, BloqCloudAlgorandApi]
    tx_details_apis = [TatumAlgorandApi, AlgoNodeAlgorandApi, BlockDaemonAlgorandApi, NodeRealAlgorandApi
        , BloqCloudAlgorandApi]
    address_txs_apis = [AlgoNodeAlgorandApi, BlockDaemonAlgorandApi, BloqCloudAlgorandApi]
    block_txs_apis = [AlgoNodeAlgorandApi, TatumAlgorandApi, NodeRealAlgorandApi, BlockDaemonAlgorandApi,
                      BloqCloudAlgorandApi]
    block_head_apis = [AlgoNodeAlgorandApi, TatumAlgorandApi, BlockDaemonAlgorandApi, NodeRealAlgorandApi]
    symbol = 'ALGO'
