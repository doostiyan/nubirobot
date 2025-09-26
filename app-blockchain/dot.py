import sys
import traceback
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from exchange.base.logging import log_event, report_exception
from exchange.base.models import Currencies
from exchange.blockchain.api.dot.polkascan import PolkascanAPI
from exchange.blockchain.api.dot.subscan import SubscanAPI
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import CurrenciesNetworkName, Transaction
from exchange.blockchain.utils import (AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError,
                                       RateLimitError, ValidationError)


class DotBlockchainInspector(Bep20BlockchainInspector):
    currency = Currencies.dot
    currency_list = [Currencies.dot]
    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    USE_EXPLORER = 'SUBSCAN'  # Available APIS: POLKASCAN, SUBSCAN

    get_balance_method = {
        CurrenciesNetworkName.DOT: 'get_wallets_balance_dot',
        CurrenciesNetworkName.BSC: 'get_wallets_balance_bsc',
    }

    get_transactions_method = {
        CurrenciesNetworkName.DOT: 'get_wallet_transactions_dot',
        CurrenciesNetworkName.BSC: 'get_wallet_transactions_bsc',
    }

    @classmethod
    def get_api(cls):
        if cls.USE_EXPLORER == 'SUBSCAN':
            return SubscanAPI.get_api(network=cls.network)
        elif cls.USE_EXPLORER == 'POLKASCAN':
            return PolkascanAPI.get_api(network=cls.network)

    @classmethod
    def get_wallets_balance_dot(cls, address_list, raise_error=False):
        balances = []
        api = cls.get_api()
        for address in address_list:
            try:
                balance = api.get_balance(address).get(Currencies.dot)
                if not balance:
                    continue
                balances.append({
                    'address': address,
                    'received': balance.get('balance'),
                    'sent': Decimal('0'),
                    'reward': Decimal('0'),
                    'balance': balance.get('balance'),
                })
            except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                    ValidationError, RateLimitError) as error:
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                if raise_error:
                    raise error
                report_exception()
        return balances

    @classmethod
    def parse_actions_dotgrid(cls, records, address):
        transactions = []
        for record in records:
            transactions.append(
                Transaction(
                    address=record.get('To'),
                    from_address=record.get('From'),
                    hash=record.get('Hash'),
                    block=record.get('Block'),
                    value=Decimal(str(record.get('Value'))),
                    timestamp=datetime.fromisoformat(record.get('Date'))
                )
            )
        return transactions

    @classmethod
    def get_wallet_transactions_dot(cls, address, network=None, raise_error=False):
        transactions = []
        api = cls.get_api()
        try:
            txs = api.get_txs(address)
            for tx in txs:
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
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            if raise_error:
                raise error
            report_exception()

    @classmethod
    def get_latest_block_addresses(cls):
        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            return set(), None, 0
        api = cls.get_api()
        try:
            response = api.get_latest_block(include_inputs=False, include_info=True)
            return response
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                ValidationError, RateLimitError) as error:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            traceback.print_exception(*sys.exc_info())
