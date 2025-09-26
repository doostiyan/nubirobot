from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from .one_contract_balance_checker import ONEContractBalanceCheckerV2Api
from .one_rpc_new import OneRpcApi, AnkrHarmonyRpc

from .one_covalent_new import ONECovalenthqAPI


class OneExplorerInterface(ExplorerInterface):
    balance_apis = [ONEContractBalanceCheckerV2Api, ONECovalenthqAPI]
    token_balance_apis = [ONECovalenthqAPI]
    token_txs_apis = [OneRpcApi]
    tx_details_apis = [AnkrHarmonyRpc, OneRpcApi]
    address_txs_apis = [OneRpcApi, ONECovalenthqAPI]
    block_txs_apis = [OneRpcApi]
    block_head_apis = [ONECovalenthqAPI, OneRpcApi]
    symbol = 'ONE'
