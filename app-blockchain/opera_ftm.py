from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from exchange.base.logging import report_exception
from exchange.blockchain.api.ftm.ftm_covalent import FantomCovalenthqAPI
from exchange.blockchain.api.ftm.ftm_ftmscan import FtmScanAPI
from exchange.blockchain.contracts_conf import opera_ftm_contract_currency, opera_ftm_contract_info
from exchange.blockchain.models import BaseBlockchainInspector, Transaction
from exchange.blockchain.utils import (AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError,
                                       RateLimitError, ValidationError)


class OperaFTMBlockchainInspector(BaseBlockchainInspector):
    """
    Based on https://docs.fantom.foundation
    """
    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    currency_list = None

    USE_EXPLORER_BALANCE_FTM = 'web3'  # Available options: covalent, web3, ftmscan
    USE_EXPLORER_TRANSACTION_FTM = 'covalent'  # Available options: covalent, web3, ftmscan, graphql

    @classmethod
    def opera_ftm_contract_currency_list(cls, network=None):
        if network is None:
            network = cls.network
        return opera_ftm_contract_currency[network]

    @classmethod
    def opera_ftm_contract_info_list(cls, network=None):
        if network is None:
            network = cls.network
        if cls.currency_list is not None:
            currency_subset = {currency: opera_ftm_contract_info[network][currency]
                               for currency in cls.currency_list if currency in opera_ftm_contract_info[network]}
            return currency_subset
        return opera_ftm_contract_info[network]

    @classmethod
    def get_fantom_api(cls, api_selection):
        from exchange.blockchain.api.ftm.ftm_web3 import FtmWeb3API
        if api_selection == 'ftmscan':
            return FtmScanAPI.get_api()
        if api_selection == 'web3':
            return FtmWeb3API.get_api()

    @classmethod
    def get_wallets_balance_ftm(cls, address_list):
        if cls.USE_EXPLORER_BALANCE_FTM == 'covalent':
            return cls.get_wallets_balance_ftm_covalent(address_list)
        if cls.USE_EXPLORER_BALANCE_FTM == 'ftmscan' or 'web3':
            return cls.get_wallets_balance_api(address_list)

    @classmethod
    def get_wallets_balance_ftm_covalent(cls, address_list, raise_error=False):
        balances = defaultdict(list)
        try:
            for address in address_list:
                res = FantomCovalenthqAPI.get_api().get_balance(address)
                for currency, contract_info in cls.opera_ftm_contract_info_list().items():
                        response = res.get(currency)
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
    def get_wallets_balance_api(cls, address_list, raise_error=False):
        balances = defaultdict(list)
        try:
            for address in address_list:
                for currency, contract_info in cls.opera_ftm_contract_info_list().items():
                        response = cls.get_fantom_api(cls.USE_EXPLORER_BALANCE_FTM).get_token_balance(address, contract_info)
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
    def get_wallet_transactions_ftm(cls, address):
        if cls.USE_EXPLORER_TRANSACTION_FTM == 'covalent':
            return cls.get_wallet_transactions_ftm_covalent(address)
        if cls.USE_EXPLORER_TRANSACTION_FTM == 'ftmscan':
            return cls.get_wallet_transactions_ftmscan(address)

    @classmethod
    def get_wallet_transactions_ftm_covalent(cls, address, raise_error=False):
        txs = defaultdict(list)
        for currency, contract_info in cls.opera_ftm_contract_info_list().items():
            try:
                transactions = FantomCovalenthqAPI.get_api().get_token_txs(address, contract_info)
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

    @classmethod
    def get_wallet_transactions_ftmscan(cls, address, raise_error=False):
        txs = defaultdict(list)
        try:
            for currency, contract_info in cls.opera_ftm_contract_info_list().items():
                transactions = FtmScanAPI.get_api(network=cls.network).get_token_txs(address, contract_info)
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
