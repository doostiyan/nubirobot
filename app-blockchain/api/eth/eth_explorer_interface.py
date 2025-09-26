from exchange.blockchain.api.eth.eth_tatum import ETHTatumApi
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface

from .eth_blockbook_new import (
    EthereumBinanceBlockbookApi,
    EthereumEthBlockBlockBookApi,
    EthereumHeatWallet1BlockBookApi,
    EthereumHeatWallet2BlockBookApi,
)
from .eth_contract_balance_checker import ETHContractBalanceCheckerV2Api
from .eth_covalent_new import ETHCovalenthqApi
from .eth_web3_new import ETHWeb3Api
from .etherscan import EtherscanAPI

# '''
# https://bitex-doc.nobitex.ir/doc/the-open-network-z8OhQfFjA6
# '''


class EthExplorerInterface(ExplorerInterface):
    balance_apis = [ETHContractBalanceCheckerV2Api, EtherscanAPI, ETHWeb3Api, ETHCovalenthqApi]
    tx_details_apis = [ETHWeb3Api, EtherscanAPI, ETHCovalenthqApi, EthereumHeatWallet1BlockBookApi,
                       EthereumHeatWallet2BlockBookApi, EthereumEthBlockBlockBookApi, EthereumBinanceBlockbookApi,
                       ETHTatumApi]
    address_txs_apis = [EtherscanAPI, ETHCovalenthqApi, EthereumHeatWallet1BlockBookApi,
                        EthereumHeatWallet2BlockBookApi, EthereumEthBlockBlockBookApi, EthereumBinanceBlockbookApi]
    block_txs_apis = [ETHWeb3Api, EtherscanAPI, EthereumHeatWallet1BlockBookApi]
    token_balance_apis = [EtherscanAPI, ETHCovalenthqApi, ETHWeb3Api]
    token_txs_apis = [EtherscanAPI, ETHCovalenthqApi, EthereumHeatWallet1BlockBookApi, EthereumHeatWallet2BlockBookApi,
                      EthereumEthBlockBlockBookApi, EthereumBinanceBlockbookApi]
    token_tx_details_apis = [ETHWeb3Api, ETHTatumApi, EthereumHeatWallet1BlockBookApi, EthereumHeatWallet2BlockBookApi,
                             EthereumEthBlockBlockBookApi, EthereumBinanceBlockbookApi]
    block_head_apis = [EtherscanAPI, ETHWeb3Api, ETHCovalenthqApi, EthereumHeatWallet1BlockBookApi, ETHTatumApi]

    symbol = 'ETH'
