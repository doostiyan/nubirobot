import sys
import traceback
from decimal import Decimal

from django.conf import settings
from exchange.base.logging import report_exception
from exchange.base.models import Currencies
from exchange.blockchain.api.ada.cardano_bitquery import CardanoBitqueryAPI
from exchange.blockchain.api.ada.cardano_blockfrost import BlockfrostAPI
from exchange.blockchain.api.ada.cardano_graphql import CardanoAPI
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import CurrenciesNetworkName, Transaction
from exchange.blockchain.utils import (AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError,
                                       RateLimitError, ValidationError)


class AdaBlockchainInspector(Bep20BlockchainInspector):
    currency = Currencies.ada
    currency_list = [Currencies.ada]

    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    USE_EXPLORER_BALANCE = 'Graphql'  # Available APIs: Graphql, Blockfrost
    USE_EXPLORER_TRANSACTIONS = 'Graphql'  # Available APIs: Graphql, Blockfrost, Bitqury
    USE_EXPLORER_BLOCKS = 'Graphql'  # Available APIs: Graphql, Blockfrost, Bitqury

    get_balance_method = {
        CurrenciesNetworkName.ADA: 'get_wallets_balance_ada',
        CurrenciesNetworkName.BSC: 'get_wallets_balance_bsc',
    }

    get_transactions_method = {
        CurrenciesNetworkName.ADA: 'get_wallet_transactions_ada',
        CurrenciesNetworkName.BSC: 'get_wallet_transactions_bsc',
    }

    get_transaction_details_method = {
        CurrenciesNetworkName.ADA: 'get_transaction_details_ada',
        CurrenciesNetworkName.BSC: 'get_transaction_details_bsc',
    }


    @classmethod
    def get_api(cls, api_selection):
        if api_selection == 'Graphql':
            return CardanoAPI.get_api(network=cls.network)
        elif api_selection == 'Blockfrost':
            return BlockfrostAPI.get_api(network=cls.network)
        elif api_selection == 'Bitquery':
            return CardanoBitqueryAPI.get_api(network=cls.network)

    @classmethod
    def get_transaction_details_ada(cls, tx_hash, network=None, raise_error=False):
        tx_details = None
        try:
            tx_details = CardanoAPI.get_api(network=cls.network).get_tx_details(tx_hash=tx_hash)
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                ValidationError, RateLimitError, Exception) as error:
            if raise_error:
                raise error
            report_exception()
        return tx_details

    @classmethod
    def get_wallets_balance_ada(cls, address_list, raise_error=False):
        balances = []
        api = cls.get_api(cls.USE_EXPLORER_BALANCE)
        try:
            response = api.get_balance(address_list)
            for balance in response:
                balances.append({
                    'address': balance.get('address'),
                    'received': balance.get('balance'),
                    'sent': Decimal('0'),
                    'reward': Decimal('0'),
                    'balance': balance.get('balance'),
                })
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                ValidationError, RateLimitError) as error:
            if raise_error:
                raise error
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            report_exception()
        return balances

    @classmethod
    def get_wallet_transactions_ada(cls, address, network=None, raise_error=False):
        transactions = []
        api = cls.get_api(cls.USE_EXPLORER_TRANSACTIONS)
        try:
            txs = api.get_txs(address)
            for tx in txs:
                tx = tx.get(Currencies.ada)
                value = tx.get('amount')
                if tx.get('direction') == 'outgoing':
                    value = - value
                transaction = Transaction(
                    address=address,
                    from_address=tx.get('from_address') if isinstance(tx.get('from_address'), list) else [
                        tx.get('from_address')],
                    block=tx.get('block'),
                    hash=tx.get('hash'),
                    timestamp=tx.get('date'),
                    value=value,
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
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            report_exception()

    @classmethod
    def get_latest_block_addresses(cls, include_inputs=False, include_info=True):
        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            return set(), None, 0
        api = cls.get_api(cls.USE_EXPLORER_BLOCKS)
        try:
            response = api.get_latest_block(include_inputs=include_inputs, include_info=include_info)
            return response
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                ValidationError, RateLimitError) as error:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            traceback.print_exception(*sys.exc_info())
