import sys
import traceback
from decimal import Decimal

import requests
from django.conf import settings
from exchange.base.logging import log_event, report_exception
from exchange.base.models import Currencies
from exchange.blockchain.api.ftm.ftm_covalent import FantomCovalenthqAPI
from exchange.blockchain.api.ftm.ftm_ftmscan import FtmScanAPI
from exchange.blockchain.api.ftm.ftm_graphql import FantomGraphQlAPI
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import Transaction
from exchange.blockchain.utils import (AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError,
                                       RateLimitError, ValidationError)


class FantomBlockchainInspector(Bep20BlockchainInspector):
    """
    Fantom Explorer.
    Based on https://explorer.fantom.network/
    """

    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    currency = Currencies.ftm
    currency_list = [Currencies.ftm]

    USE_EXPLORER_BALANCE_FTM = 'ftmscan'  # Available options: covalent, graphql, web3, ftmscan
    USE_EXPLORER_TRANSACTION_FTM = 'ftmscan'  # Available options: Covalent, graphql, ftmscan
    USE_EXPLORER_BLOCKS = 'web3'  # Available APIs: web3, graphql

    get_balance_method = {
        'FTM': 'get_wallets_balance_ftm',
        'BSC': 'get_wallets_balance_bsc',
    }

    get_transactions_method = {
        'FTM': 'get_wallet_transactions_ftm',
        'BSC': 'get_wallet_transactions_bsc',
    }

    @classmethod
    def get_api_ftm(cls, api_selection):
        from exchange.blockchain.api.ftm.ftm_web3 import FtmWeb3API
        if api_selection == 'graphql':
            return FantomGraphQlAPI.get_api()
        if api_selection == 'web3':
            return FtmWeb3API.get_api()
        if api_selection == 'ftmscan':
            return FtmScanAPI.get_api()
        if api_selection == 'covalent':
            return FantomCovalenthqAPI.get_api()

    @classmethod
    def get_wallets_balance_ftm(cls, address_list):
        if cls.USE_EXPLORER_BALANCE_FTM == 'ftmscan':
            return cls.get_wallets_balance_ftmscan(address_list)
        if cls.USE_EXPLORER_BALANCE_FTM == 'covalent':
            return cls.get_wallets_balance_covalent(address_list)
        if cls.USE_EXPLORER_BALANCE_FTM == 'web3' or 'graphql':
            return cls.get_wallets_balance_api(address_list)
        return cls.get_wallets_balance_ftmscan(address_list)

    @classmethod
    def get_wallets_balance_ftmscan(cls, address_list, raise_error=False):
        balances = []
        api = FtmScanAPI.get_api()
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
            report_exception()
        return balances

    @classmethod
    def get_wallets_balance_covalent(cls, address_list, raise_error=False):
        balances = []
        api = FantomCovalenthqAPI.get_api()
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
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            if raise_error:
                raise error
            report_exception()
        return balances


    @classmethod
    def get_wallets_balance_api(cls, address_list, raise_error=False):
        balances = []
        api = cls.get_api_ftm(cls.USE_EXPLORER_BALANCE_FTM)
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
            report_exception()
        return balances

    @classmethod
    def get_wallet_transactions_ftm(cls, address, raise_error=False):
        transactions = []
        api = cls.get_api_ftm(cls.USE_EXPLORER_TRANSACTION_FTM)
        try:
            txs = api.get_txs(address)
            for tx in txs:
                tx = tx.get(Currencies.ftm)
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
            report_exception()
        return transactions

    @classmethod
    def get_latest_block_addresses(cls):
        api = cls.get_api_ftm(cls.USE_EXPLORER_BLOCKS)
        try:
            response = api.get_latest_block(include_inputs=True, include_info=True)
            return response
        except Exception as error:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            traceback.print_exception(*sys.exc_info())
