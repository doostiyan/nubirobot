from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from .base_contract_balance_checker import BaseContractBalanceCheckerV2Api

from .base_publicnode import AlchemyBaseApi
from .basescan_base import BaseScanAPI
from .routescan_base import BaseRouteScanAPI
from .tatum_base import BaseTatumApi


class BaseExplorerInterface(ExplorerInterface):
    balance_apis = [BaseContractBalanceCheckerV2Api, AlchemyBaseApi, BaseRouteScanAPI, BaseTatumApi, BaseScanAPI]
    tx_details_apis = [AlchemyBaseApi, BaseTatumApi, BaseRouteScanAPI, BaseScanAPI]
    token_tx_details_apis = [AlchemyBaseApi, BaseTatumApi]
    token_txs_apis = [BaseScanAPI]
    address_txs_apis = [BaseScanAPI, BaseRouteScanAPI]
    block_txs_apis = [AlchemyBaseApi, BaseRouteScanAPI, BaseScanAPI]
    block_head_apis = [AlchemyBaseApi, BaseRouteScanAPI, BaseTatumApi, BaseScanAPI]
    symbol = 'ETH'
    network = 'BASE'
