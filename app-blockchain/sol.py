import sys
import traceback
from decimal import Decimal

from django.conf import settings
from exchange.base.logging import log_event, report_exception
from exchange.base.models import Currencies
from exchange.blockchain.api.sol.sol_bitquery import SolanaBitqueryAPI
from exchange.blockchain.api.sol.sol_getblock import SolanaGetBlockAPI
from exchange.blockchain.api.sol.sol_rpc import AlchemyRPC, AnkrRPC, MainRPC, QuickNodeRPC, SerumRPC, ShadowRPC
from exchange.blockchain.api.sol.sol_solanabeach import SolanaBeachAPI
from exchange.blockchain.api.sol.sol_solscan import SolScanAPI
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.models import CurrenciesNetworkName, Transaction
from exchange.blockchain.utils import (AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError,
                                       RateLimitError, ValidationError)


class SolanaBlockchainInspector(Bep20BlockchainInspector):
    currency = Currencies.sol
    currency_list = [Currencies.sol]
    minimum_sol_in_transactions = 0.001

    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    USE_EXPLORER_BALANCE = 'MainRPC'  # Available APIS: MainRPC, get_block, AnkrRPC, SerumRPC, QuickNodeRPC, SCAN, BEACH
    USE_EXPLORER_TRANSACTIONS = 'SerumRPC'  # Available APIS: BEACH, SCAN, ShadowRPC, SerumRPC, AnkrRPC, QuickNodeRPC, AlchemyRPC
    USE_EXPLORER_BLOCKS = 'BITQUERY'  # Available APIS: SerumRPC, QuickNodeRPC, AnkrRPC, BITQUERY, AlchemyRPC, ShadowRPC

    batch_supporter_api = {'MainRPC', 'get_block', 'AnkrRPC', 'SerumRPC', 'QuickNodeRPC'}

    sol_apis = {'MainRPC': MainRPC.get_api, 'AnkrRPC': AnkrRPC.get_api, 'SerumRPC': SerumRPC.get_api,
                'QuickNodeRPC': QuickNodeRPC.get_api, 'AlchemyRPC': AlchemyRPC.get_api, 'ShadowRPC': ShadowRPC.get_api,
                'SCAN': SolScanAPI.get_api, 'BITQUERY': SolanaBitqueryAPI.get_api, 'BEACH': SolanaBeachAPI.get_api,
                'get_block': SolanaGetBlockAPI.get_api}

    get_balance_method = {
        CurrenciesNetworkName.SOL: 'get_wallets_balance_sol',
        CurrenciesNetworkName.BSC: 'get_wallets_balance_bsc',
    }

    get_transactions_method = {
        CurrenciesNetworkName.SOL: 'get_wallet_transactions_sol',
        CurrenciesNetworkName.BSC: 'get_wallet_transactions_bsc',
    }

    @classmethod
    def get_api_sol(cls, api_selection):
        return cls.sol_apis[api_selection](network=cls.network)

    @classmethod
    def get_wallets_balance_sol(cls, address_list, raise_error=False):

        if cls.USE_EXPLORER_BALANCE in cls.batch_supporter_api:
            return cls.get_wallets_balance_batch_sol(address_list)
        api = cls.get_api_sol(cls.USE_EXPLORER_BALANCE)
        balances = []
        for address in address_list:
            try:
                balance = api.get_balance(address).get(Currencies.sol)
                if not balance:
                    continue
                balances.append({
                    'address': address,
                    'received': balance.get('amount'),
                    'sent': Decimal('0'),
                    'rewarded': Decimal('0'),
                    'balance': balance.get('amount'),
                })
            except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                    ValidationError, RateLimitError) as error:
                if raise_error:
                    raise error
        return balances

    @classmethod
    def get_wallets_balance_batch_sol(cls, address_list, raise_error=False):
        balances = []
        api = cls.get_api_sol(cls.USE_EXPLORER_BALANCE)
        for i in range(0, len(address_list), api.get_balance_limit):
            addresses = address_list[i:i + api.get_balance_limit]
            try:
                api_balances = api.get_balances(addresses)
                for balance in api_balances:
                    balance = balance.get(Currencies.sol)
                    balances.append({
                        'address': balance.get('address'),
                        'received': balance.get('amount'),
                        'sent': Decimal('0'),
                        'rewarded': Decimal('0'),
                        'balance': balance.get('amount'),
                    })
            except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                    ValidationError, RateLimitError) as error:
                if raise_error:
                    raise error
        return balances

    @classmethod
    def get_wallet_transactions_sol(cls, address, network=None, raise_error=False):
        transactions = []
        api = cls.get_api_sol(cls.USE_EXPLORER_TRANSACTIONS)
        try:
            txs = api.get_txs(address)
            for tx in txs:
                if float(tx.get('amount')) < cls.minimum_sol_in_transactions:
                    continue
                transaction = Transaction(
                    address=address,
                    from_address=[tx.get('from_address')],
                    block=tx.get('block'),
                    hash=tx.get('hash'),
                    timestamp=tx.get('date'),
                    value=tx.get('amount'),
                    confirmations=tx.get('confirmations'),
                    is_double_spend=False,
                    details=tx.get('raw'),
                )
                transactions.append(transaction)
            return transactions
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                ValidationError, RateLimitError) as error:
            if raise_error:
                raise error

    @classmethod
    def get_latest_block_addresses(cls, include_inputs=False, include_info=True):
        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            return set(), None, 0
        try:
            api = cls.get_api_sol(cls.USE_EXPLORER_BLOCKS)
            response = api.get_latest_block(include_inputs=include_inputs, include_info=include_info)
            return response
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                ValidationError, RateLimitError) as error:
            traceback.print_exception(*sys.exc_info())
