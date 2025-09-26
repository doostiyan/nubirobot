from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.erc20 import Erc20BlockchainInspector


class ShibBlockchainInspector(Erc20BlockchainInspector, Bep20BlockchainInspector):
    """ Based on: etherscan.io
        Rate limit: ? requests/sec
    """
    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    currency = Currencies.shib
    currency_list = [Currencies.shib]

    # Key bellow must be same as CURRENCY_INFO in coins_info.py
    get_balance_method = {
        'ETH': 'get_wallets_balance_eth',
        'BSC': 'get_wallets_balance_bsc',
    }
    get_transactions_method = {
        'ETH': 'get_wallet_transactions_eth',
        'BSC': 'get_wallet_transactions_bsc',
    }
    get_transaction_details_method = {
        'ETH': 'get_transaction_details_eth',
        'BSC': 'get_transaction_details_bsc',
    }
