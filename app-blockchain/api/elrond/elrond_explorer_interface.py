from exchange.blockchain.api.elrond.bitquery_elrond import BitqueryElrondApi
from exchange.blockchain.api.elrond.elrond_api import ElrondApi
from exchange.blockchain.api.elrond.gateway_elrond import GatewayElrondApi
from exchange.blockchain.api.elrond.multiversx import MultiversxApi
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface


class ElrondExplorerInterface(ExplorerInterface):
    balance_apis = [ElrondApi, GatewayElrondApi]
    tx_details_apis = [GatewayElrondApi, BitqueryElrondApi, ElrondApi]
    address_txs_apis = [ElrondApi, GatewayElrondApi, MultiversxApi, BitqueryElrondApi]
    block_txs_apis = [GatewayElrondApi, ElrondApi]
    block_head_apis = [ElrondApi, GatewayElrondApi, MultiversxApi, BitqueryElrondApi]
    symbol = 'EGLD'
