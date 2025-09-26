from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.apt.aptoslabs_graphql import GraphQlAptosApi
from exchange.blockchain.api.apt.aptoslabs_apt import AptoslabsAptApi
from exchange.blockchain.api.apt.chainbase_apt import AptosChainbase
from exchange.blockchain.api.apt.nodereal_apt import AptosNodeReal
from exchange.blockchain.api.apt.apscan_apt import ApscanApi


class AptosExplorerInterface(ExplorerInterface):
    balance_apis = [AptoslabsAptApi]
    tx_details_apis = [AptoslabsAptApi, ApscanApi, AptosChainbase, AptosNodeReal]
    address_txs_apis = [GraphQlAptosApi, ApscanApi]
    block_txs_apis = [GraphQlAptosApi, AptosChainbase, AptoslabsAptApi]
    block_head_apis = [AptoslabsAptApi, AptosChainbase, GraphQlAptosApi]
    symbol = 'APT'
    USE_BLOCK_HEAD_API = True
