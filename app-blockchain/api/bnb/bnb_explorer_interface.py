from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.bnb.bnb_beacon_chain import BeaconChainApi
from exchange.blockchain.api.bnb.binance_new import BnbBinanceApi


class BnbExplorerInterface(ExplorerInterface):
    tx_details_apis = [BeaconChainApi, BnbBinanceApi]
    address_txs_apis = [BnbBinanceApi]
    balance_apis = [BnbBinanceApi]
    block_head_apis = [BnbBinanceApi]
    symbol = 'BNB'
