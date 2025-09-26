from collections import defaultdict

from exchange.base.models import Currencies, SUPPORTED_INVOICE_CURRENCIES, get_currency_codename, ALL_CRYPTO_CURRENCIES
from exchange.blockchain.aave import AaveBlockchainInspector
from exchange.blockchain.ada import AdaBlockchainInspector
from exchange.blockchain.atom import AtomBlockchainInspector
from exchange.blockchain.bch import BitcoinCashBlockchainInspector
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.bnb import BinanceCoinBlockchainInspector
from exchange.blockchain.btc import BitcoinBlockchainInspector
from exchange.blockchain.dai import DaiBlockchainInspector
from exchange.blockchain.doge import DogecoinBlockchainInspector
from exchange.blockchain.dot import DotBlockchainInspector
from exchange.blockchain.eos import EOSBlockchainInspector
from exchange.blockchain.erc20 import Erc20BlockchainInspector
from exchange.blockchain.etc import ETCBlockchainInspector
from exchange.blockchain.eth import EthereumBlockchainInspector
from exchange.blockchain.explorer import BlockchainExplorer
from exchange.blockchain.ftm import FantomBlockchainInspector
from exchange.blockchain.grt import TheGraphBlockchainInspector
from exchange.blockchain.link import ChainLinkBlockchainInspector
from exchange.blockchain.ltc import LitecoinBlockchainInspector
from exchange.blockchain.opera_ftm import OperaFTMBlockchainInspector
from exchange.blockchain.one import OneBlockchainInspector
from exchange.blockchain.pmn import PaymonBlockchainInspector
from exchange.blockchain.polygon import PolygonBlockchainInspector
from exchange.blockchain.polygon_erc20 import PolygonERC20BlockchainInspector
from exchange.blockchain.shib import ShibBlockchainInspector
from exchange.blockchain.sol import SolanaBlockchainInspector
from exchange.blockchain.trx import TRXBlockchainInspector
from exchange.blockchain.uni import UniswapBlockchainInspector
from exchange.blockchain.usdt import TetherBlockchainInspector
from exchange.blockchain.validators import validate_crypto_address_v2
from exchange.blockchain.xlm import XLMBlockchainInspector
from exchange.blockchain.xrp import RippleBlockchainInspector
from exchange.blockchain.algo import AlgoBlockchainInspector


# class OmniTetherBlockchainInspector(BaseBlockchainInspector):
#     """ Based on: https://api.omniexplorer.info
#         Rate limit: .2 requests/sec
#     """
#
#     @classmethod
#     def get_wallets_balance(cls, address_list):
#         time.sleep(3)
#         balances = []
#         try:
#             api_response = cls.get_session().post(
#                 'https://api.omniexplorer.info/v2/address/addr/', data={'addr': address_list}, timeout=10)
#             api_response.raise_for_status()
#         except Exception as e:
#             print('Failed to get Tether wallet balance from omniexplorer.info API: {}'.format(str(e)))
#             time.sleep(1)
#             report_event('OmniExplorer API Error')
#             return
#         response_info = list(api_response.json().items())
#         # Check for error
#         if not response_info:
#             print('Failed to get Tether wallet balance from omniexplorer.info API')
#             time.sleep(1)
#             report_event('OmniExplorer API Error')
#             return
#         err, msg = response_info[0]
#         if err == 'error':
#             print('Failed to get Tether wallet balance from omniexplorer.info API: {}'.format(str(msg)))
#             time.sleep(1)
#             report_event('OmniExplorer API Error')
#             return
#
#         for address, addr_info in response_info:
#             addr_balances = addr_info['balance']
#             balance = Decimal('0')
#             # Check for only tether balance of an address!
#             # id(31) is usdt in omni protocol!
#             for addr_balance in addr_balances:
#                 if addr_balance['id'] != '31':
#                     continue
#                 balance = Decimal(addr_balance['value']) / Decimal('1e8')
#                 break
#             # TODO: currently we only return balance and set other fields to zero
#             balances.append({
#                 'address': address,
#                 'received': balance,
#                 'sent': Decimal('0'),
#                 'balance': balance,
#             })
#         return balances
#
#     @classmethod
#     def get_wallet_transactions(cls, address):
#         time.sleep(3)
#         address_endpoint = 'https://api.omniexplorer.info/v1/transaction/address/0'
#         try:
#             api_response = cls.get_session().post(address_endpoint, data={'addr': address}, timeout=10)
#             api_response.raise_for_status()
#             info = api_response.json()
#             info = info.get('transactions')
#         except Exception as e:
#             print('Failed to get Tether wallet transactions from API: {}'.format(str(e)))
#             report_event('OmniExplorer API Error')
#             return None
#
#         transactions = []
#         for tx in info:
#             if tx.get('referenceaddress') != address or tx.get('propertyid') != 31 or not tx.get('valid'):
#                 continue
#             tx_datetime = parse_utc_timestamp(tx.get('blocktime'))
#             transactions.append(Transaction(
#                 address=address,
#                 hash=tx.get('txid'),
#                 timestamp=tx_datetime,
#                 value=Decimal(tx.get('amount')),
#                 confirmations=tx.get('confirmations'),
#                 is_double_spend=False,  # TODO: check for double spends for USDT
#                 details=tx,
#             ))
#         return transactions


class BlockchainInspector:
    # Add Currencies and Networks in alphabetical order

    USE_NEW_STRUCTURE = True

    CURRENCY_CLASSES = {
        Currencies.btc: BitcoinBlockchainInspector,
        Currencies.eth: EthereumBlockchainInspector,
        Currencies.ltc: LitecoinBlockchainInspector,
        Currencies.usdt: TetherBlockchainInspector,
        Currencies.xrp: RippleBlockchainInspector,
        Currencies.bch: BitcoinCashBlockchainInspector,
        Currencies.bnb: BinanceCoinBlockchainInspector,
        Currencies.eos: EOSBlockchainInspector,
        Currencies.xlm: XLMBlockchainInspector,
        Currencies.etc: ETCBlockchainInspector,
        Currencies.trx: TRXBlockchainInspector,
        Currencies.pmn: PaymonBlockchainInspector,
        Currencies.doge: DogecoinBlockchainInspector,
        Currencies.uni: UniswapBlockchainInspector,
        Currencies.aave: AaveBlockchainInspector,
        Currencies.link: ChainLinkBlockchainInspector,
        Currencies.dai: DaiBlockchainInspector,
        Currencies.grt: TheGraphBlockchainInspector,
        Currencies.dot: DotBlockchainInspector,
        Currencies.ada: AdaBlockchainInspector,
        Currencies.shib: ShibBlockchainInspector,
        Currencies.ftm: FantomBlockchainInspector,
        Currencies.pol: PolygonBlockchainInspector,
        Currencies.one: OneBlockchainInspector,
        Currencies.sol: SolanaBlockchainInspector,
        Currencies.atom: AtomBlockchainInspector,
        Currencies.algo: AlgoBlockchainInspector,
    }

    for currency in ALL_CRYPTO_CURRENCIES:
        if currency not in CURRENCY_CLASSES:
            CURRENCY_CLASSES[currency] = type(
                get_currency_codename(currency).upper() + 'BlockchainInspector',
                (Erc20BlockchainInspector,
                 Bep20BlockchainInspector,
                 OperaFTMBlockchainInspector,
                 PolygonERC20BlockchainInspector),
                {
                    'currency': currency,
                    'currency_list': [currency],
                    'get_balance_method': {
                        'ETH': 'get_wallets_balance_eth',
                        'BSC': 'get_wallets_balance_bsc',
                        'FTM': 'get_wallets_balance_ftm',
                        'MATIC': 'get_wallets_balance_polygon',
                    },
                    'get_transactions_method': {
                        'ETH': 'get_wallet_transactions_eth',
                        'BSC': 'get_wallet_transactions_bsc',
                        'FTM': 'get_wallet_transactions_ftm',
                        'MATIC': 'get_wallet_transactions_polygon',
                    },
                    'get_transaction_details_method': {
                        'ETH': 'get_transaction_details_eth',
                        'BSC': 'get_transaction_details_bsc',
                    },
                }
            )

    @classmethod
    def get_wallets_balance(cls, address_list, currency, is_segwit=False):
        """
        address_list: can be a list of couples or a dict. To be clear, you can call this function call it like this:
        BlockchainInspector.get_wallets_balance([('some_address', 'ETH'), ('some_other_address', 'BSC')], currency=42)
        or like this:
        BlockchainInspector.get_wallets_balance({'ETH': ['some_address']}, currency=11)
        """
        address_list_per_network = address_list
        if not isinstance(address_list, dict):
            address_list_per_network = {}
            for address in address_list:
                if isinstance(address, str):
                    if currency == Currencies.one:
                        is_valid, network = validate_crypto_address_v2(address, currency=Currencies.eth)
                    else:
                        is_valid, network = validate_crypto_address_v2(address, currency)
                elif isinstance(address, tuple):
                    if currency == Currencies.one:
                        is_valid, network = validate_crypto_address_v2(address[0], currency=Currencies.eth,
                                                                       network='ETH')
                    else:
                        is_valid, network = validate_crypto_address_v2(address[0], currency, network=address[1])
                    address, network = address
                else:
                    is_valid, network = (False, None)
                if is_valid:
                    address_list_per_network.setdefault(network, []).append(address)
        res_balances = defaultdict(list)
        for network in address_list_per_network:
            address_list = address_list_per_network.get(network)
            if network != 'ZTRX':
                balances = BlockchainExplorer.get_wallets_balance({network: address_list}, currency)
            else:
                if network in cls.CURRENCY_CLASSES[currency].ignore_network_list:
                    continue
                balances = getattr(cls.CURRENCY_CLASSES[currency],
                                   cls.CURRENCY_CLASSES[currency].get_balance_method.get(network))(address_list) or {}
            if isinstance(balances, list):
                balances = {currency: balances}
            for currency, currency_balances in balances.items():
                res_balances[currency].extend(currency_balances)
        return res_balances

    @classmethod
    def get_wallet_transactions(cls, address, currency, retry=False, network=None, contract_address=None):
        if network == 'ONE' or currency == Currencies.one:
            is_valid, network_based_on_address = validate_crypto_address_v2(address, currency=Currencies.eth,
                                                                            network='ETH')
        else:
            is_valid, network_based_on_address = validate_crypto_address_v2(address, currency)
        if network is None:
            network = network_based_on_address
        if cls.USE_NEW_STRUCTURE:
            txs = BlockchainExplorer.get_wallet_transactions(address, currency=currency, network=network, contract_address=contract_address)
            return txs
        if currency == Currencies.btc:
            if is_valid and network == 'BSC':
                return cls.CURRENCY_CLASSES[currency].get_wallet_transactions(address, network)

            # Main explorer for BTC transaction details is blockcypher
            txs = BitcoinBlockchainInspector.get_wallet_transactions(address, network)

            if txs is None and retry:
                txs = BitcoinBlockchainInspector.get_wallet_transactions_blockbook(address)
            return txs
        return cls.CURRENCY_CLASSES[currency].get_wallet_transactions(address, network)

    @classmethod
    def get_transaction_details(cls, tx_hash, currency, network=None):
        tx = cls.CURRENCY_CLASSES[currency].get_transaction_details(tx_hash, network)
        return tx

    @classmethod
    def get_invoice_status(cls, invoice, currency, retry=False):
        if not invoice:
            return
        if currency not in SUPPORTED_INVOICE_CURRENCIES:
            return None
        return cls.CURRENCY_CLASSES[currency].get_invoice_status(invoice_hash=invoice)
