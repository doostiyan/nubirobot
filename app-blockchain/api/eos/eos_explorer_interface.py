from decimal import Decimal

from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.eos.new_eos_sweden import EosSwedenApi
from exchange.blockchain.api.eos.new_eos_greymass import EosGreymassApi


class EosExplorerInterface(ExplorerInterface):
    balance_apis = [EosSwedenApi]
    tx_details_apis = [EosSwedenApi, EosGreymassApi]
    address_txs_apis = [EosGreymassApi, EosSwedenApi]
    symbol = 'EOS'
    min_valid_tx_amount = Decimal('0.0005')
