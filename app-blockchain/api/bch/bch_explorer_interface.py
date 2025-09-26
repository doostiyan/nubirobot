from decimal import Decimal

from exchange.blockchain.api.general.explorer_interface import ExplorerInterface

from .bch_bitquery import BitcoinCashBitqueryAPI
from .bch_blockbook_new import BitcoinCashBlockBookApi
from .bch_blockchair import BitcoinCashBlockchairApi
from .bch_haskoin import BitcoinCashHaskoinApi
from .bch_rest import BitcoinCashRestApi


class BitcoinCashExplorerInterface(ExplorerInterface):
    balance_apis = [BitcoinCashRestApi, BitcoinCashBlockBookApi, BitcoinCashBitqueryAPI]
    tx_details_apis = [BitcoinCashBlockBookApi, BitcoinCashHaskoinApi, BitcoinCashBlockchairApi]
    address_txs_apis = [BitcoinCashBlockBookApi, BitcoinCashBlockchairApi]
    block_txs_apis = [BitcoinCashBlockBookApi, BitcoinCashBitqueryAPI]
    block_head_apis = [BitcoinCashBlockBookApi, BitcoinCashBitqueryAPI]
    symbol = 'BCH'
    min_valid_tx_amount = Decimal('0.003')
