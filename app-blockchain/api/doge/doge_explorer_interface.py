from decimal import Decimal

from exchange.blockchain.api.general.explorer_interface import ExplorerInterface

from .doge_bitquery import DogeBitqueryAPI
from .doge_block_book import DogeBlockBookApi
from .doge_blockcypher_new import DogeBlockcypherApi
from .doge_tatum import DogeTatumApi


class DogeExplorerInterface(ExplorerInterface):
    balance_apis = [DogeBlockBookApi, DogeBlockcypherApi, DogeBitqueryAPI]
    tx_details_apis = [DogeBlockcypherApi, DogeBlockBookApi, DogeTatumApi]
    address_txs_apis = [DogeBlockBookApi]
    block_txs_apis = [DogeBlockBookApi, DogeBitqueryAPI]
    block_head_apis = [DogeBlockBookApi, DogeBitqueryAPI, DogeTatumApi]
    min_valid_tx_amount = Decimal('1.00000000')
    symbol = 'DOGE'
