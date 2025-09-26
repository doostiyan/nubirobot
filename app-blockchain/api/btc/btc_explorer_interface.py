from decimal import Decimal
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from .btc_blockbook_new import BitcoinBlockBookAPI
from .btc_blockcypher_new import BitcoinBlockcypherAPI
from .btc_haskoin_new import BitcoinHaskoinAPI
from .btc_bitquery import BtcBitqueryAPI
from .btc_tatum import BitcoinTatumApi


class BTCExplorerInterface(ExplorerInterface):
    balance_apis = [BitcoinBlockBookAPI, BtcBitqueryAPI]
    tx_details_apis = [BitcoinBlockBookAPI, BitcoinHaskoinAPI, BitcoinBlockcypherAPI, BitcoinTatumApi]
    address_txs_apis = [BitcoinBlockBookAPI]
    block_txs_apis = [BitcoinBlockBookAPI, BtcBitqueryAPI]
    block_head_apis = [BitcoinBlockBookAPI, BtcBitqueryAPI, BitcoinTatumApi]
    min_valid_tx_amount = Decimal('0.0005')
    symbol = 'BTC'
