import datetime
import pytz

from exchange.base.models import Currencies
from exchange.blockchain.api.atom.atom_node import AtomscanNode, AtomAllthatnode
from exchange.blockchain.cosmos_general import CosmosGeneralBlockchainInspector
from exchange.blockchain.models import CurrenciesNetworkName


class AtomBlockchainInspector(CosmosGeneralBlockchainInspector):
    currency = Currencies.atom
    currency_list = [Currencies.atom]
    currency_name = 'ATOM'

    # Available options: node
    USE_EXPLORER_BALANCE = 'node'
    USE_EXPLORER_TRANSACTION = 'node'

    # options: AtomscanNode, CosmosNetworkNode, FigmentNode, AtomAllthatnode
    PROVIDER_BALANCE = AtomAllthatnode
    PROVIDER_TRANSACTION = AtomscanNode

    get_balance_method = {
        CurrenciesNetworkName.ATOM: 'call_api_balances',
        CurrenciesNetworkName.BSC: 'get_wallets_balance_bsc',
    }

    get_transactions_method = {
        CurrenciesNetworkName.ATOM: 'call_api_wallet_txs',
        CurrenciesNetworkName.BSC: 'get_wallet_transactions_bsc',
    }

    @classmethod
    def get_wallet_withdraws(cls, address):
        withdraws = super().get_wallet_withdraw_node(address)
        start_time = pytz.timezone('UTC').localize(datetime.datetime.utcnow()) - datetime.timedelta(
            hours=3)  # now -3 hours , UTC base because api outputs are in UTC
        withdraws = [wtd for wtd in withdraws if wtd.timestamp > start_time]
        return withdraws
