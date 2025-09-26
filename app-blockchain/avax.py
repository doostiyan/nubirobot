import sys
import traceback
from decimal import Decimal

import requests
from django.conf import settings
from exchange.base.logging import report_exception
from exchange.base.models import Currencies
from exchange.blockchain.api.avax.avalanchescan import AvalancheScanAPI
from exchange.blockchain.api.avax.avax_covalent import AvalancheCovalenthqAPI
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import Transaction
from exchange.blockchain.utils import (AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError,
                                       RateLimitError, ValidationError)


class AvaxBlockchainInspector(Bep20BlockchainInspector):
    """
    Avalanche Explorer.
    """

    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    currency = Currencies.avax
    currency_list = [Currencies.avax]

    USE_EXPLORER_BALANCE_AVAX = 'covalent'  # Available options: covalent, web3, avalanche_scan
    USE_EXPLORER_TRANSACTION_AVAX = 'avalanche_scan'  # Available options: covalent, avalanche_scan
    USE_EXPLORER_BLOCKS = 'web3'  # Available APIs: web3, avalanche_scan

    get_balance_method = {
        'AVAX': 'get_wallets_balance_avax',
        'BSC': 'get_wallets_balance_bsc',
    }

    get_transactions_method = {
        'AVAX': 'get_wallet_transactions_avax',
        'BSC': 'get_wallet_transactions_bsc',
    }

    @classmethod
    def get_avax_api(cls, api_selection):
        from exchange.blockchain.api.avax.avalanche_web3 import AvalancheWeb3API
        if api_selection == 'web3':
            return AvalancheWeb3API.get_api()
        if api_selection == 'avalanche_scan':
            return AvalancheScanAPI.get_api()
        if api_selection == 'covalent':
            return AvalancheCovalenthqAPI.get_api()

    @classmethod
    def get_wallets_balance_avax(cls, address_list):
        if cls.USE_EXPLORER_BALANCE_AVAX == 'avalanche_scan':
            return cls.get_wallets_balance_avax_scan(address_list)
        if cls.USE_EXPLORER_BALANCE_AVAX == 'covalent':
            return cls.get_wallets_balance_covalent(address_list)
        if cls.USE_EXPLORER_BALANCE_AVAX == 'web3':
            return cls.get_wallets_balance_web3(address_list)
        return cls.get_wallets_balance_avax_scan(address_list)

    @classmethod
    def get_wallets_balance_avax_scan(cls, address_list, raise_error=False):
        balances = []
        api = AvalancheScanAPI.get_api()
        try:
            responses = api.get_balances(address_list)
            for response in responses:
                balances.append({
                    'address': response.get('address'),
                    'balance': response.get('balance'),
                    'received': response.get('balance'),
                    'sent': Decimal('0'),
                    'rewarded': Decimal('0'),
                })
        except Exception as error:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            if raise_error:
                raise error
        return balances

    @classmethod
    def get_wallets_balance_covalent(cls, address_list, raise_error=False):
        balances = []
        api = AvalancheCovalenthqAPI.get_api()
        try:
            for address in address_list:
                res = api.get_balance(address)
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
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
        return balances

    @classmethod
    def get_wallets_balance_web3(cls, address_list, raise_error=False):
        from exchange.blockchain.api.avax.avalanche_web3 import AvalancheWeb3API
        balances = []
        api = AvalancheWeb3API.get_api()
        try:
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
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            if raise_error:
                raise error
        return balances

    @classmethod
    def get_wallet_transactions_avax(cls, address, raise_error=False):
        transactions = []
        api = cls.get_avax_api(cls.USE_EXPLORER_TRANSACTION_AVAX)
        try:
            txs = api.get_txs(address)
            for tx in txs:
                tx = tx.get(Currencies.avax)
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
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            if raise_error:
                raise error
        return transactions

    @classmethod
    def get_latest_block_addresses(cls):
        api = cls.get_avax_api(cls.USE_EXPLORER_BLOCKS)
        try:
            response = api.get_latest_block(include_inputs=True, include_info=True)
            return response
        except Exception as error:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            traceback.print_exception(*sys.exc_info())
