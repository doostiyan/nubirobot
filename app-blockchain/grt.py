from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.erc20 import Erc20BlockchainInspector


class TheGraphBlockchainInspector(Erc20BlockchainInspector):
    """ Based on: etherscan.io
        Rate limit: ? requests/sec
    """
    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    currency = Currencies.grt
    currency_list = [Currencies.grt]

    # Key bellow must be same as CURRENCY_INFO in coins_info.py
    get_balance_method = {
        'ETH': 'get_wallets_balance_eth',
    }
    get_transactions_method = {
        'ETH': 'get_wallet_transactions_eth',
    }
    get_transaction_details_method = {
        'ETH': 'get_transaction_details_eth',
    }
