from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.hedera.hedera_mirrornode import MirrorNodeHederaApi
from exchange.blockchain.api.hedera.hedera_graphql import GraphqlHederaApi
from exchange.blockchain.api.hedera.hedera_mirrornode import QuickNodeHederaApi


class HederaExplorerInterface(ExplorerInterface):
    balance_apis = [MirrorNodeHederaApi, GraphqlHederaApi, QuickNodeHederaApi]
    tx_details_apis = [MirrorNodeHederaApi, GraphqlHederaApi, QuickNodeHederaApi]
    address_txs_apis = [GraphqlHederaApi, MirrorNodeHederaApi, QuickNodeHederaApi]
    block_txs_apis = []
    block_head_apis = []
    symbol = 'HBAR'
    USE_AGGREGATION_SERVICE = True