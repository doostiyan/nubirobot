from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from exchange.base.logging import log_event, report_exception
from exchange.blockchain.api.polygon.polyganscan import PolygonScanAPI
from exchange.blockchain.api.polygon.polygon_covalent import PolygonCovalenthqAPI
from exchange.blockchain.contracts_conf import polygon_ERC20_contract_currency, polygon_ERC20_contract_info
from exchange.blockchain.models import BaseBlockchainInspector, Transaction
from exchange.blockchain.utils import (AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError,
                                       RateLimitError, ValidationError)


class PolygonERC20BlockchainInspector(BaseBlockchainInspector):

    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    currency_list = None

    USE_EXPLORER_BALANCE_POLYGON = 'web3'  # Available options: covalent, web3, polygonscan
    USE_EXPLORER_TRANSACTION_POLYGON = 'covalent'  # Available options: covalent, polygonscan

    @classmethod
    def polygon_erc20_contract_currency_list(cls, network=None):
        if network is None:
            network = cls.network
        return polygon_ERC20_contract_currency[network]

    @classmethod
    def polygon_erc20_contract_info_list(cls, network=None):
        if network is None:
            network = cls.network
        if cls.currency_list is not None:
            currency_subset = {currency: polygon_ERC20_contract_info[network][currency]
                               for currency in cls.currency_list if currency in polygon_ERC20_contract_info[network]}
            return currency_subset
        return polygon_ERC20_contract_info[network]

    @classmethod
    def get_polygon_api(cls, api_selection):
        from exchange.blockchain.api.polygon.polygon_web3 import PolygonWeb3API
        if api_selection == 'polygonscan':
            return PolygonScanAPI.get_api()
        if api_selection == 'web3':
            return PolygonWeb3API.get_api()
        if api_selection == 'covalent':
            return PolygonCovalenthqAPI.get_api()
        return PolygonCovalenthqAPI.get_api()

    @classmethod
    def get_wallets_balance_polygon(cls, address_list):
        if cls.USE_EXPLORER_BALANCE_POLYGON == 'covalent':
            return cls.get_wallets_balance_polygon_covalent(address_list)
        if cls.USE_EXPLORER_BALANCE_POLYGON == 'polygonscan':
            return cls.get_wallets_balance_polygon_polygonscan(address_list)
        if cls.USE_EXPLORER_BALANCE_POLYGON == 'web3':
            return cls.get_wallets_balance_polygon_web3(address_list)

    @classmethod
    def get_wallets_balance_polygon_covalent(cls, address_list, raise_error=False):
        balances = defaultdict(list)
        for address in address_list:
            result = PolygonCovalenthqAPI.get_api().get_balance(address)
            for currency, contract_info in cls.polygon_erc20_contract_info_list().items():
                try:
                    response = result.get(currency)
                    if not response:
                        continue
                    balances[currency].append({
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
    def get_wallets_balance_polygon_web3(cls, address_list, raise_error=False):
        from exchange.blockchain.api.polygon.polygon_web3 import PolygonWeb3API
        balances = defaultdict(list)
        for address in address_list:
            for currency, contract_info in cls.polygon_erc20_contract_info_list().items():
                try:
                    response = PolygonWeb3API.get_api().get_token_balance(address, contract_info)
                    if not response:
                        continue
                    balances[currency].append({
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
    def get_wallets_balance_polygon_polygonscan(cls, address_list, raise_error=False):
        balances = defaultdict(list)
        for address in address_list:
            for currency, contract_info in cls.polygon_erc20_contract_info_list().items():
                try:
                    response = PolygonScanAPI.get_api().get_token_balance(address, contract_info)
                    if not response:
                        continue
                    balances[currency].append({
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
    def get_wallet_transactions_polygon(cls, address, raise_error=False):
        txs = defaultdict(list)
        api = cls.get_polygon_api(cls.USE_EXPLORER_TRANSACTION_POLYGON)
        for currency, contract_info in cls.polygon_erc20_contract_info_list().items():
            try:
                transactions = api.get_token_txs(address, contract_info)
                for tx_info in transactions:
                    tx = tx_info.get(currency)
                    if tx is None:
                        continue
                    txs[currency].append(Transaction(
                        address=address,
                        from_address=tx.get('from_address'),
                        hash=tx.get('hash'),
                        block=tx.get('block'),
                        timestamp=tx.get('date'),
                        value=tx.get('amount'),
                        confirmations=tx.get('confirmations'),
                        details=tx.get('raw')
                    ))
            except Exception as error:
                if raise_error:
                    raise error
        return txs
