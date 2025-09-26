from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.polygon.pol_contract_balance_checker import POLContractBalanceCheckerV2Api
from exchange.blockchain.api.polygon.polygon_web3_new import PolygonWeb3Api
from exchange.blockchain.api.polygon.polygon_covalent_new import PolygonCovalentAPI
from exchange.blockchain.api.polygon.polygon_scan_new import PolygonBlockScanAPI


class PolygonExplorerInterface(ExplorerInterface):
    balance_apis = [POLContractBalanceCheckerV2Api, PolygonWeb3Api, PolygonCovalentAPI, PolygonBlockScanAPI]
    token_balance_apis = [PolygonWeb3Api, PolygonCovalentAPI, PolygonBlockScanAPI]
    tx_details_apis = [PolygonWeb3Api, PolygonBlockScanAPI, PolygonCovalentAPI]
    address_txs_apis = [PolygonBlockScanAPI, PolygonCovalentAPI]
    token_txs_apis = [PolygonBlockScanAPI, PolygonCovalentAPI]
    block_txs_apis = [PolygonWeb3Api, PolygonBlockScanAPI]
    block_head_apis = [PolygonCovalentAPI, PolygonWeb3Api, PolygonBlockScanAPI]
    symbol = 'MATIC'
