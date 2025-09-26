from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.sonic.sonic_contract_balance_checker import SonicContractBalanceCheckerV2Api
from exchange.blockchain.api.sonic.sonic_publicnode import SonicPublicNodeWeb3API
from exchange.blockchain.api.sonic.sonic_scan import SonicScanApi


class SonicExplorerInterface(ExplorerInterface):
    balance_apis: list = [SonicContractBalanceCheckerV2Api, SonicScanApi]
    tx_details_apis: list = [SonicPublicNodeWeb3API, SonicScanApi]
    address_txs_apis: list = [SonicScanApi]
    block_txs_apis: list = [SonicPublicNodeWeb3API, SonicScanApi]
    block_head_apis: list = [SonicPublicNodeWeb3API, SonicScanApi]
    symbol: str = 'SONIC'
