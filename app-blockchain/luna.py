from exchange.base.models import Currencies
from exchange.blockchain.api.terra.terra_node import TerraNode
from exchange.blockchain.cosmos_general import CosmosGeneralBlockchainInspector
from exchange.blockchain.models import CurrenciesNetworkName


class LunaBlockchainInspector(CosmosGeneralBlockchainInspector):
    currency = Currencies.luna
    currency_name = 'LUNA'
    # Available options: node
    USE_EXPLORER_BALANCE = 'node'
    USE_EXPLORER_TRANSACTION = 'node'
    # Available options: TerraNode
    PROVIDER_BALANCE = TerraNode
    PROVIDER_TRANSACTION = TerraNode

    get_balance_method = {
        CurrenciesNetworkName.LUNA: 'get_wallets_balance',
    }

    get_transactions_method = {
        CurrenciesNetworkName.LUNA: 'get_wallet_transactions',
    }
