from decimal import Decimal
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.tezos.tzkt_tezos import TzktTezosAPI
from exchange.blockchain.api.tezos.tzstats_tezos import TzstatsTezosAPI
from exchange.blockchain.api.tezos.bitquery_tezos import BitQueryTezosApi


class TezosExplorerInterface(ExplorerInterface):
    balance_apis = [TzktTezosAPI, BitQueryTezosApi, TzstatsTezosAPI]
    tx_details_apis = [TzktTezosAPI, BitQueryTezosApi, TzstatsTezosAPI]
    address_txs_apis = [TzktTezosAPI, TzstatsTezosAPI]
    block_txs_apis = [TzktTezosAPI, TzstatsTezosAPI, BitQueryTezosApi]
    block_head_apis = [TzstatsTezosAPI, TzktTezosAPI, BitQueryTezosApi]
    symbol = 'XTZ'
    min_valid_tx_amount = Decimal('0.01')
