from exchange.blockchain.api.ftm.ftm_contract_balance_checker import FTMContractBalanceCheckerV2Api
from exchange.blockchain.api.ftm.ftm_covalenthq import FtmCovalenthqApi
from exchange.blockchain.api.ftm.ftm_scan import FtmScanApi
from exchange.blockchain.api.ftm.ftm_web3_new import FtmWeb3Api
from exchange.blockchain.api.ftm.ftm_graphql_new import FtmGraphqlApi
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.general.general import GeneralApi


class FTMExplorerInterface(ExplorerInterface):
    block_head_apis: [GeneralApi] = [FtmGraphqlApi, FtmWeb3Api, FtmScanApi, FtmCovalenthqApi]
    balance_apis: [GeneralApi] = [FTMContractBalanceCheckerV2Api, FtmScanApi,FtmWeb3Api, FtmGraphqlApi, FtmCovalenthqApi]
    address_txs_apis: [GeneralApi] = [FtmScanApi, FtmCovalenthqApi]
    token_txs_apis: [GeneralApi] = [FtmScanApi]
    block_txs_apis: [GeneralApi] = [FtmWeb3Api, FtmScanApi]
    tx_details_apis: [GeneralApi] = [FtmWeb3Api, FtmScanApi, FtmCovalenthqApi]
    symbol = 'FTM'
