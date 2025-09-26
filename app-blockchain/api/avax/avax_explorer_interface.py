from exchange.blockchain.api.general.explorer_interface import ExplorerInterface

from .avax_contract_balance_checker import AVAXContractBalanceCheckerV2Api
from .avax_covalent_new import AvalancheCovalentAPI
from .avax_oklink import AvalancheOkLinkApi
from .avax_scan import AvaxScanApi
from .avax_web3_new import AvalancheWeb3API


class AvalancheExplorerInterface(ExplorerInterface):
    balance_apis = [AVAXContractBalanceCheckerV2Api, AvalancheCovalentAPI, AvalancheWeb3API, AvalancheOkLinkApi]
    tx_details_apis = [AvalancheWeb3API, AvalancheCovalentAPI, AvalancheOkLinkApi, AvaxScanApi]
    address_txs_apis = [AvaxScanApi, AvalancheOkLinkApi, AvalancheCovalentAPI]
    block_txs_apis = [AvalancheWeb3API, AvalancheCovalentAPI, AvalancheOkLinkApi, AvaxScanApi]
    token_balance_apis = [AvalancheCovalentAPI, AvalancheOkLinkApi, AvalancheWeb3API]
    token_txs_apis = [AvaxScanApi, AvalancheOkLinkApi, AvalancheCovalentAPI]
    block_head_apis = [AvalancheCovalentAPI, AvalancheWeb3API, AvalancheOkLinkApi, AvaxScanApi]
    symbol = 'AVAX'
