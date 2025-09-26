from exchange.blockchain.api.bsc.bsc_contract_balance_checker import BSCContractBalanceCheckerV2Api
from exchange.blockchain.api.bsc.bsc_covalent_new import BSCCovalentApi
from exchange.blockchain.api.bsc.bsc_oklink import OkLinkBscApi
from exchange.blockchain.api.bsc.bsc_scan_new import BSCBlockScanAPI
from exchange.blockchain.api.bsc.bsc_web3_new import BSCWeb3Api
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface


class BscExplorerInterface(ExplorerInterface):
    balance_apis = [BSCContractBalanceCheckerV2Api, BSCWeb3Api, BSCBlockScanAPI, BSCCovalentApi]
    token_balance_apis = [BSCWeb3Api, BSCBlockScanAPI, BSCCovalentApi]
    tx_details_apis = [BSCWeb3Api, BSCBlockScanAPI, BSCCovalentApi]
    address_txs_apis = [BSCBlockScanAPI, OkLinkBscApi, BSCCovalentApi]
    token_txs_apis = [BSCBlockScanAPI, OkLinkBscApi, BSCCovalentApi]
    block_txs_apis = [BSCWeb3Api, BSCBlockScanAPI, BSCCovalentApi]
    block_head_apis = [BSCBlockScanAPI, OkLinkBscApi, BSCWeb3Api, BSCCovalentApi]
    staking_apis = [BSCWeb3Api]
    symbol = 'BNB'
    network = 'BSC'
