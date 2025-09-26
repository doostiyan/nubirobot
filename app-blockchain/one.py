import sys
import traceback
from decimal import Decimal

import requests
from django.conf import settings
from exchange.base.logging import log_event, report_exception
from exchange.base.models import Currencies
from exchange.blockchain.api.one.one_covalent import ONECovalenthqAPI
from exchange.blockchain.api.one.one_rpc import HarmonyRPC
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.models import Transaction
from exchange.blockchain.utils import (AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError,
                                       RateLimitError, ValidationError)


class OneBlockchainInspector(Bep20BlockchainInspector):
    """
    Harmony Explorer.
    """

    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    currency = Currencies.one
    currency_list = [Currencies.one]

    USE_EXPLORER_BALANCE_ONE = 'covalent'  # Available options: covalent, web3, one_rpc
    USE_EXPLORER_TRANSACTION_ONE = 'one_rpc'  # Available options: covalent, one_rpc
    USE_EXPLORER_BLOCKS = 'web3'  # Available APIs: web3, one_rpc

    get_balance_method = {
        'ONE': 'get_wallets_balance_one',
        'BSC': 'get_wallets_balance_bsc',

    }

    get_transactions_method = {
        'ONE': 'get_wallet_transactions_one',
        'BSC': 'get_wallet_transactions_bsc',
    }

    @classmethod
    def get_one_api(cls, api_selection):
        from exchange.blockchain.api.one.one_web3 import OneWeb3API
        if api_selection == 'web3':
            return OneWeb3API.get_api()
        if api_selection == 'one_rpc':
            return HarmonyRPC.get_api()
        if api_selection == 'covalent':
            return ONECovalenthqAPI.get_api()

    @classmethod
    def get_wallets_balance_one(cls, address_list):
        if cls.USE_EXPLORER_BALANCE_ONE == 'covalent':
            return cls.get_wallets_balance_covalent(address_list)
        if cls.USE_EXPLORER_BALANCE_ONE == 'web3':
            return cls.get_wallets_balance_web3(address_list)
        return cls.get_wallets_balance_covalent(address_list)

    @classmethod
    def get_wallets_balance_covalent(cls, address_list, raise_error=False):
        balances = []
        try:
            for address in address_list:
                res = ONECovalenthqAPI.get_api().get_balance(address)
                response = res.get(cls.currency)
                if not response:
                    continue
                balances.append({
                    'address': response.get('address'),
                    'balance': response.get('amount'),
                    'received': response.get('amount'),
                    'sent': Decimal('0'),
                    'rewarded': Decimal('0'),
                })
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                ValidationError, RateLimitError) as error:
            if raise_error:
                raise error
        return balances

    @classmethod
    def get_wallets_balance_web3(cls, address_list, raise_error=False):
        from exchange.blockchain.api.one.one_web3 import OneWeb3API
        balances = []
        try:
            api = OneWeb3API.get_api()
            for address in address_list:
                response = api.get_balance(address)
                if not response:
                    continue
                balances.append({
                    'address': response.get('address'),
                    'balance': response.get('balance'),
                    'received': response.get('balance'),
                    'sent': Decimal('0'),
                    'rewarded': Decimal('0'),
                })
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                ValidationError, RateLimitError) as error:
            if raise_error:
                raise error
        return balances

    @classmethod
    def get_wallet_transactions_one(cls, address, raise_error=False):
        transactions = []

        api = cls.get_one_api(cls.USE_EXPLORER_TRANSACTION_ONE)
        try:
            txs = api.get_txs(address)
            for tx in txs:
                tx = tx.get(Currencies.one)
                transactions.append(Transaction(
                    address=address,
                    from_address=tx.get('from_address'),
                    hash=tx.get('hash'),
                    block=tx.get('block'),
                    timestamp=tx.get('date'),
                    value=tx.get('amount'),
                    confirmations=tx.get('confirmations'),
                    is_double_spend=False,
                    details=tx.get('raw'),
                ))
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                requests.exceptions.Timeout, requests.exceptions.Timeout) as error:
            if raise_error:
                raise error
        return transactions

    @classmethod
    def get_latest_block_addresses(cls):
        try:
            api = cls.get_one_api(cls.USE_EXPLORER_BLOCKS)
            response = api.get_latest_block(include_inputs=True, include_info=True)
            return response
        except Exception as error:
            traceback.print_exception(*sys.exc_info())
