import sys
import traceback
from decimal import Decimal

import requests
from django.conf import settings
from exchange.base.logging import report_exception
from exchange.base.models import Currencies
from exchange.blockchain.api.algorand.algo_rpc import AlgoNodeRPC, BloqCloudRPC, PureStakeRPC, RandLabsRPC
from exchange.blockchain.models import BaseBlockchainInspector, Transaction
from exchange.blockchain.utils import (AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError,
                                       RateLimitError, ValidationError)


class AlgoBlockchainInspector(BaseBlockchainInspector):
    """
    Algorand Explorer.
    """

    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    currency = Currencies.algo
    currency_list = [Currencies.algo]

    USE_EXPLORER_BALANCE_ALGO = 'pure_stake'  # Available options: algo_node, rand_labs, bloq_cloud
    USE_EXPLORER_TRANSACTION_ALGO = 'algo_node'  # Available options: pure_stake, rand_labs, bloq_cloud
    USE_EXPLORER_BLOCKS = 'rand_labs'  # Available APIs: pure_stake, algo_node, bloq_cloud

    get_balance_method = {
        'ALGO': 'get_wallets_balance_algo_rpc',
    }

    get_transactions_method = {
        'ALGO': 'get_wallet_transactions_algo_rpc',
    }

    @classmethod
    def get_algo_api(cls, api_selection):
        if api_selection == 'pure_stake':
            return PureStakeRPC.get_api()
        if api_selection == 'algo_node':
            return AlgoNodeRPC.get_api()
        if api_selection == 'rand_labs':
            return RandLabsRPC.get_api()
        if api_selection == 'bloq_cloud':
            return BloqCloudRPC.get_api()

    @classmethod
    def get_wallets_balance_algo_rpc(cls, address_list, raise_error=False):
        balances = []
        api = cls.get_algo_api(cls.USE_EXPLORER_BALANCE_ALGO)
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
            report_exception()
        return balances

    @classmethod
    def get_wallet_transactions_algo_rpc(cls, address, raise_error=False):
        transactions = []

        api = cls.get_algo_api(cls.USE_EXPLORER_TRANSACTION_ALGO)
        try:
            txs = api.get_txs(address)
            for tx in txs:
                tx = tx.get(Currencies.algo)
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
            report_exception()
        return transactions

    @classmethod
    def get_latest_block_addresses(cls):
        try:
            api = cls.get_algo_api(cls.USE_EXPLORER_BLOCKS)
            response = api.get_latest_block(include_inputs=True, include_info=True)
            return response
        except Exception as error:
            traceback.print_exception(*sys.exc_info())
