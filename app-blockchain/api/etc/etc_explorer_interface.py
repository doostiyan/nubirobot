from exchange.blockchain.api.etc.etc_web3 import EtcWeb3Api
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface

from exchange.blockchain.api.etc.etc_blockscout_graphql import EtcBlockscoutGraphqlEtcApi

from .etc_blockbook import EthereumClassicBlockBookApi
from .etc_contract_balance_checker import ETCContractBalanceCheckerV2Api


class EtcExplorerInterface(ExplorerInterface):
    balance_apis = [ETCContractBalanceCheckerV2Api, EthereumClassicBlockBookApi]
    tx_details_apis = [EtcWeb3Api, EthereumClassicBlockBookApi, EtcBlockscoutGraphqlEtcApi]
    address_txs_apis = [EthereumClassicBlockBookApi]
    block_txs_apis = [EthereumClassicBlockBookApi, EtcWeb3Api]
    block_head_apis = [EtcWeb3Api,  EthereumClassicBlockBookApi]
    symbol = 'ETC'
