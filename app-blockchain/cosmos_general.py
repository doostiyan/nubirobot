from decimal import Decimal

from django.conf import settings
from exchange.base.logging import report_exception
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.models import Transaction


class CosmosGeneralBlockchainInspector(Bep20BlockchainInspector):
    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    apis = {
        'node': {
            'balance_method': 'get_wallets_balance_node',
            'wallet_transactions_method': 'get_wallet_transactions_node',
        }
    }
    currency_name = ''
    currency = None
    USE_EXPLORER_BALANCE = None
    USE_EXPLORER_TRANSACTION = None
    PROVIDER_BALANCE = None
    PROVIDER_TRANSACTION = None

    @classmethod
    def call_api_balances(cls, address_list, raise_error=False):
        selected_balance_method_name = cls.apis.get(cls.USE_EXPLORER_BALANCE).get('balance_method')
        balance_result = None
        try:
            balance_result = getattr(cls, selected_balance_method_name)(address_list)
        except Exception as error:
            if raise_error:
                raise error
        return balance_result

    @classmethod
    def call_api_wallet_txs(cls, address, raise_error=False, **kwargs):
        selected_txs_method_name = cls.apis.get(cls.USE_EXPLORER_TRANSACTION).get('wallet_transactions_method')
        txs_result = None
        try:
            txs_result = getattr(cls, selected_txs_method_name)(address)
        except Exception as err:
            if raise_error:
                raise err
        return txs_result

    @classmethod
    def get_wallets_balance_node(cls, address_list):
        balances = []
        for address in address_list:
            response = cls.PROVIDER_BALANCE.get_api().get_balance(address)
            response = response.get(cls.currency)
            if not response:
                continue
            balances.append({
                'address': response.get('address'),
                'balance': response.get('amount'),
                'received': response.get('amount'),
                'sent': Decimal('0'),
                'rewarded': Decimal('0'),
            })
        return balances

    @classmethod
    def get_wallet_transactions_node(cls, address):
        txs = cls.PROVIDER_TRANSACTION.get_api().get_txs(address)
        return cls.transaction_from_dict(txs)

    @classmethod
    def transaction_from_dict(cls, txs):
        transactions = []
        for tx in txs:
            tx = tx.get(cls.currency)
            transactions.append(Transaction(
                address=tx.get('address'),
                hash=tx.get('hash'),
                from_address=tx.get('from_address'),
                value=tx.get('amount'),
                block=tx.get('block'),
                timestamp=tx.get('date'),
                confirmations=tx.get('confirmations'),
                is_double_spend=False,
                details=tx.get('raw'),
                tag=tx.get('memo')
            ))
        return transactions

    @classmethod
    def get_wallet_withdraw_node(cls, address):
        txs = cls.PROVIDER_TRANSACTION.get_api().get_txs(address, tx_direction_filter='outgoing')
        return cls.transaction_from_dict(txs)
