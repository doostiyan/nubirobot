from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.erc20 import Erc20BlockchainInspector
from exchange.blockchain.opera_ftm import OperaFTMBlockchainInspector
from exchange.blockchain.polygon_erc20 import PolygonERC20BlockchainInspector


class AaveBlockchainInspector(Erc20BlockchainInspector, Bep20BlockchainInspector, OperaFTMBlockchainInspector,
                              PolygonERC20BlockchainInspector):
    """ Based on: etherscan.io
        Rate limit: ? requests/sec
    """
    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    currency = Currencies.aave
    currency_list = [Currencies.aave]

    # Key bellow must be same as CURRENCY_INFO in coins_info.py
    get_balance_method = {
        'ETH': 'get_wallets_balance_eth',
        'BSC': 'get_wallets_balance_bsc',
        'FTM': 'get_wallets_balance_ftm',
        'MATIC': 'get_wallets_balance_polygon',
    }
    get_transactions_method = {
        'ETH': 'get_wallet_transactions_eth',
        'BSC': 'get_wallet_transactions_bsc',
        'FTM': 'get_wallet_transactions_ftm',
        'MATIC': 'get_wallet_transactions_polygon',
    }
    get_transaction_details_method = {
        'ETH': 'get_transaction_details_eth',
        'BSC': 'get_transaction_details_bsc',
    }
