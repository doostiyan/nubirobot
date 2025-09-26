import sys
import traceback
from decimal import Decimal

import requests
from django.conf import settings
from exchange.base.logging import log_event, report_exception
from exchange.base.models import Currencies
from exchange.blockchain.api.polygon.polyganscan import PolygonScanAPI
from exchange.blockchain.api.polygon.polygon_covalent import PolygonCovalenthqAPI
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.erc20 import Erc20BlockchainInspector
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import Transaction
from exchange.blockchain.utils import (AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError,
                                       RateLimitError, ValidationError)


class PolygonBlockchainInspector(Bep20BlockchainInspector, Erc20BlockchainInspector):
    """
    Polygon Explorer.
    """

    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    currency = Currencies.pol
    currency_list = [Currencies.pol]

    USE_EXPLORER_BALANCE_POLYGON = 'web3'  # Available options: covalent, web3, polygonscan
    USE_EXPLORER_TRANSACTION_POLYGON = 'polygonscan'  # Available options: covalent, polygonscan
    USE_EXPLORER_BLOCKS = 'web3'  # Available APIs: web3, polygonscan

    get_balance_method = {
        'MATIC': 'get_wallets_balance_polygon',
        'BSC': 'get_wallets_balance_bsc',
        'ETH': 'get_wallets_balance_eth',
    }

    get_transactions_method = {
        'MATIC': 'get_wallet_transactions_polygon',
        'BSC': 'get_wallet_transactions_bsc',
        'ETH': 'get_wallet_transactions_eth',
    }

    @classmethod
    def get_polygon_api(cls, api_selection):
        from exchange.blockchain.api.polygon.polygon_web3 import PolygonWeb3API
        if api_selection == 'web3':
            return PolygonWeb3API.get_api()
        if api_selection == 'polygonscan':
            return PolygonScanAPI.get_api()
        if api_selection == 'covalent':
            return PolygonCovalenthqAPI.get_api()

    @classmethod
    def get_wallets_balance_polygon(cls, address_list):
        if cls.USE_EXPLORER_BALANCE_POLYGON == 'polygonscan':
            return cls.get_wallets_balance_polygonscan(address_list)
        if cls.USE_EXPLORER_BALANCE_POLYGON == 'covalent':
            return cls.get_wallets_balance_covalent(address_list)
        if cls.USE_EXPLORER_BALANCE_POLYGON == 'web3':
            return cls.get_wallets_balance_web3(address_list)
        return cls.get_wallets_balance_polygonscan(address_list)

    @classmethod
    def get_wallets_balance_polygonscan(cls, address_list, raise_error=False):
        balances = []
        api = PolygonScanAPI.get_api()
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
            if raise_error:
                raise error
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
        return balances

    @classmethod
    def get_wallets_balance_covalent(cls, address_list, raise_error=False):
        balances = []
        api = PolygonCovalenthqAPI.get_api()
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
        from exchange.blockchain.api.polygon.polygon_web3 import PolygonWeb3API
        balances = []
        api = PolygonWeb3API.get_api()
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
            if raise_error:
                raise error
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
        return balances

    @classmethod
    def get_wallet_transactions_polygon(cls, address, raise_error=False):
        transactions = []
        api = cls.get_polygon_api(cls.USE_EXPLORER_TRANSACTION_POLYGON)
        try:
            txs = api.get_txs(address)
            for tx in txs:
                tx = tx.get(Currencies.pol)
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
        api = cls.get_polygon_api(cls.USE_EXPLORER_BLOCKS)
        try:
            response = api.get_latest_block(include_inputs=True, include_info=True)
            return response
        except Exception as error:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            traceback.print_exception(*sys.exc_info())
