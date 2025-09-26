from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.xlm.stellar_explorer import StellarExplorerApi
from exchange.blockchain.api.xlm.blockchair_new import StellarBlockchairAPI
from exchange.blockchain.api.xlm.horizon_new import StellarHorizonAPI


class StellarExplorerInterface(ExplorerInterface):
    balance_apis = [StellarHorizonAPI]
    tx_details_apis = [StellarBlockchairAPI, StellarExplorerApi]
    address_txs_apis = [StellarHorizonAPI]
    block_head_apis = [StellarBlockchairAPI]
    symbol = 'XLM'
