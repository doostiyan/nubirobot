from exchange.blockchain.api.flow.flow_bitquery import FlowBitqueryApi
from exchange.blockchain.api.flow.flow_node import FlowNodeApi
from exchange.blockchain.api.flow.flowdriver import FlowdriverApi
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface


class FlowExplorerInterface(ExplorerInterface):
    balance_apis = [FlowBitqueryApi, FlowNodeApi]
    tx_details_apis = [FlowNodeApi, FlowdriverApi]
    address_txs_apis = [FlowBitqueryApi, FlowdriverApi]
    block_txs_apis = [FlowNodeApi, FlowBitqueryApi]
    block_head_apis = [FlowNodeApi, FlowBitqueryApi]
    symbol = 'FLOW'
    USE_AGGREGATION_SERVICE = True
