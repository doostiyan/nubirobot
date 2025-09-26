from decimal import Decimal

from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.xmr.monero_new import MoneroAPI


class XmrExplorerInterface(ExplorerInterface):
    balance_apis = [MoneroAPI]
    tx_details_apis = [MoneroAPI]
    address_txs_apis = [MoneroAPI]
    block_txs_apis = [MoneroAPI]
    block_head_apis = [MoneroAPI]
    symbol = 'XMR'
    min_valid_tx_amount = Decimal('0.001')
