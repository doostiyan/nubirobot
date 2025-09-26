from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from exchange.base.logging import log_event, report_exception
from exchange.blockchain.api.one.one_covalent import ONECovalenthqAPI
from exchange.blockchain.api.one.one_rpc import HarmonyRPC
from exchange.blockchain.contracts_conf import harmony_ERC20_contract_currency, harmony_ERC20_contract_info
from exchange.blockchain.models import BaseBlockchainInspector, Transaction
from exchange.blockchain.utils import (AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError,
                                       RateLimitError, ValidationError)


class OneERC20BlockchainInspector(BaseBlockchainInspector):
    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    currency_list = None

    USE_EXPLORER_BALANCE_ONE = 'web3'  # Available options: covalent, web3
    USE_EXPLORER_TRANSACTION_ONE = 'one_rpc'  # Available options: covalent, one_rpc

    @classmethod
    def harmony_erc20_contract_currency_list(cls, network=None):
        if network is None:
            network = cls.network
        return harmony_ERC20_contract_currency[network]

    @classmethod
    def harmony_erc20_contract_info_list(cls, network=None):
        if network is None:
            network = cls.network
        if cls.currency_list is not None:
            currency_subset = {currency: harmony_ERC20_contract_info[network][currency]
                               for currency in cls.currency_list if currency in harmony_ERC20_contract_info[network]}
            return currency_subset
        return harmony_ERC20_contract_info[network]

    @classmethod
    def get_one_api(cls, api_selection):
        from exchange.blockchain.api.one.one_web3 import OneWeb3API
        if api_selection == 'one_rpc':
            return HarmonyRPC.get_api()
        if api_selection == 'web3':
            return OneWeb3API.get_api()
        if api_selection == 'covalent':
            return ONECovalenthqAPI.get_api()
        return ONECovalenthqAPI.get_api()

    @classmethod
    def get_wallets_balance_one(cls, address_list):
        if cls.USE_EXPLORER_BALANCE_ONE == 'covalent':
            return cls.get_wallets_balance_one_covalent(address_list)
        if cls.USE_EXPLORER_BALANCE_ONE == 'web3':
            return cls.get_wallets_balance_one_web3(address_list)

    @classmethod
    def get_wallets_balance_one_covalent(cls, address_list, raise_error=False):
        balances = defaultdict(list)
        for address in address_list:
            result = ONECovalenthqAPI.get_api().get_balance(address)
            for currency, contract_info in cls.harmony_erc20_contract_info_list().items():
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
    def get_wallets_balance_one_web3(cls, address_list, raise_error=False):
        from exchange.blockchain.api.one.one_web3 import OneWeb3API
        balances = defaultdict(list)
        for address in address_list:
            for currency, contract_info in cls.harmony_erc20_contract_info_list().items():
                try:
                    response = OneWeb3API.get_api().get_token_balance(address, contract_info)
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
    def get_wallet_transactions_one(cls, address, raise_error=False):
        txs = defaultdict(list)
        api = cls.get_one_api(cls.USE_EXPLORER_TRANSACTION_ONE)
        for currency, contract_info in cls.harmony_erc20_contract_info_list().items():
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
