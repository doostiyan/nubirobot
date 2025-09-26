import datetime
import time
from collections import defaultdict
from decimal import Decimal

import pytz
from django.conf import settings
from django.utils.dateparse import parse_datetime
from exchange.base.logging import log_event, report_event, report_exception
from exchange.base.models import Currencies
from exchange.blockchain.api.xrp.xrp_rpc import RippleRpcAPI
from exchange.blockchain.models import BaseBlockchainInspector, Transaction


class RippleBlockchainInspector(BaseBlockchainInspector):
    """ Based on: https://data.ripple.com
        Rate limit: Not mentioned
    """
    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'

    get_balance_method = {
        'XRP': 'get_wallets_balance_xrp',
    }

    @classmethod
    def get_wallets_balance(cls, address_list_per_network):
        balances = []
        for network in address_list_per_network:
            address_list = address_list_per_network.get(network)
            balances.extend(getattr(cls, cls.get_balance_method.get(network))(address_list) or [])
        return balances

    @classmethod
    def get_explorer_url(cls):
        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            explorer_url = 'http://testnet.data.api.ripple.com/'
        else:
            explorer_url = 'https://data.ripple.com/'

        return explorer_url

    @classmethod
    def get_wallets_balance_ripple_ledger(cls, address_list, raise_error=False):
        """
            Note: this function only returns net balances for each address and not sent/etc. details in order to make
                  fewer API call
        """
        time.sleep(0.5)
        balances = []
        for address in address_list:
            time.sleep(1)
            try:
                explorer_url = cls.get_explorer_url() + 'v2/accounts/{}/balances?currency=XRP'
                api_response = cls.get_session().get(
                    explorer_url.format(address), timeout=5)
                api_response.raise_for_status()
                balance = Decimal(api_response.json()['balances'][0]['value'])
            except Exception as e:
                if raise_error:
                    raise e
                print('Failed to get XRP wallet balance from data.ripple API: {}'.format(str(e)))
                # report_event('Ripple API Error')
                time.sleep(1)
                continue
            # TODO: currently we only return balance and set other fields to zero
            balances.append({
                'address': address,
                'received': balance,
                'sent': Decimal('0'),
                'balance': balance,
            })
        return balances

    @classmethod
    def get_wallets_balance_xrp(cls, address_list):
        return cls.get_wallets_balance_ripple_ledger(address_list)

    @classmethod
    def get_wallet_transactions(cls, address, network=None):
        return cls.get_wallet_transactions_rpc(address, network=network)

    @classmethod
    def get_wallet_transactions_ledger(cls, address, network=None, raise_error=False):
        # TODO: cannot recognize if total transaction of address are more than 200
        time.sleep(0.1)
        try:
            start_time = datetime.datetime.utcnow() - datetime.timedelta(hours=4)
            explorer_url = cls.get_explorer_url() + 'v2/accounts/{}/payments?type=received&currency=xrp&start={}&limit=700'
            api_response = cls.get_session().get(
                explorer_url.format(
                    address,
                    start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
                ),
                timeout=60,
            )
            api_response.raise_for_status()
            info = api_response.json()
        except Exception as e:
            if raise_error:
                raise e
            print('Failed to get XRP wallet transactions from API: {}'.format(str(e)))
            report_exception()
            return None
        if info.get('result') != "success":
            # report_event('Ripple API Result Error')
            return None
        txs = info.get('payments')
        if not txs:
            return []

        return cls.parse_payments(txs, address)

    @classmethod
    def get_wallet_transactions_rpc(cls, address, network=None, raise_error=False):
        txs = defaultdict(list)
        try:
            transactions = RippleRpcAPI.get_api(network=cls.network).get_txs(address=address, limit=200)
            for tx_info in transactions:
                tx = tx_info.get(Currencies.xrp)
                if tx is None:
                    continue
                txs[Currencies.xrp].append(Transaction(
                    address=address,
                    from_address=[tx.get('from_address')],
                    hash=tx.get('hash'),
                    timestamp=tx.get('date'),
                    value=tx.get('amount'),
                    confirmations=tx.get('confirmations'),
                    details=tx.get('raw'),
                    tag=tx.get('memo'),
                ))
        except Exception as error:
            if raise_error:
                raise error
            report_exception()
        return txs

    @classmethod
    def parse_payments(cls, payments, address=None, return_withdraws=False):
        transactions = []
        for tx_info in payments:
            delivered_amount = tx_info.get('delivered_amount')
            if not delivered_amount:
                continue
            if isinstance(delivered_amount, dict):
                continue
            tag = tx_info.get('destination_tag')
            if not tag and not return_withdraws:  # without tag deposit is not okay but withdraw is
                continue
            if tx_info.get('issuer') and tx_info.get('issuer') != tx_info.get('source'):
                # report_event('[RippleInspector:parse_payments] Issuer does not equal to source')
                continue

            if tx_info.get('currency') != "XRP":
                # report_event('[RippleInspector:parse_payments] currency does not equal to xrp, currency: {}, source_currency: {}'.format(tx_info.get('currency'), tx_info.get('source_currency')))
                continue

            value = Decimal('0')
            if address:
                destination = tx_info.get('destination')
                source = tx_info.get('source')
                if source == address:
                    value = -Decimal(delivered_amount)
                elif destination == address:
                    value = Decimal(delivered_amount)

            transactions.append(Transaction(
                address=address,
                from_address=[tx_info.get('source')],
                hash=tx_info.get('tx_hash'),
                timestamp=parse_datetime(tx_info.get('executed_time')),
                value=value,
                confirmations=0,
                is_double_spend=False,  # TODO check for double spend
                details=tx_info,
                tag=int(tag) if tag else None,
            ))
        return transactions

    @classmethod
    def parse_actions_xrpdataripple(cls, records, address):
        transactions = []
        for record in records:
            delivered_amount = record.get('delivered_amount')
            if not delivered_amount:
                continue
            if isinstance(delivered_amount, dict):
                continue
            tag = record.get('destination_tag')
            if not tag:
                continue
            if record.get('issuer') and record.get('issuer') != record.get('source'):
                # report_event('[RippleInspector:parse_payments] Issuer does not equal to source')
                continue

            if record.get('currency') != "XRP":
                # report_event('[RippleInspector:parse_payments] currency does not equal to xrp, currency: {}, source_currency: {}'.format(tx_info.get('currency'), tx_info.get('source_currency')))
                continue
            transactions.append(
                Transaction(
                    address=record.get('destination'),
                    from_address=record.get('source'),
                    hash=record.get('tx_hash'),
                    value=Decimal(record.get('delivered_amount')),
                    timestamp=parse_datetime(record.get('executed_time')),
                    confirmations=0,
                    is_double_spend=False,
                    details=record,
                    tag=int(tag),
                )
            )
        return transactions

    @classmethod
    def get_transaction_from_blockchain(cls, tx_hash, raise_error=False):
        """Returns the raw response from blockchain explorer"""
        # Get tx from data.ripple.com
        if not isinstance(tx_hash, str):
            # report_event('[RippleInspector:get_transaction] Tx is not string.')
            return None
        try:
            explorer_url = cls.get_explorer_url() + '/v2/transactions/{}'.format(tx_hash)
            api_response = cls.get_session().get(
                explorer_url,
                timeout=60,
            )
            api_response.raise_for_status()
            info = api_response.json()
        except Exception as e:
            if raise_error:
                raise e
            print('Failed to get XRP transaction from API: {}'.format(str(e)))
            # report_event('[RippleInspector:get_transaction] Ripple API Error')
            return None
        if info.get('result') != "success":
            # report_event('[RippleInspector:get_transaction] Ripple API Result Error')
            return None
        tx_info = info.get('transaction')

        # Check transaction hash
        if tx_info.get('hash') != tx_hash:
            # report_event('[RippleInspector:get_transaction] Ripple API Result Incorrectly!!')
            return None

        return tx_info

    @classmethod
    def verify_transaction(cls, tx):
        """Gets transaction and returns the validated transaction object"""
        if isinstance(tx, str):
            tx = cls.get_transaction_from_blockchain(tx)
        if tx and isinstance(tx, dict):
            # Validate response
            tx_data = tx.get('tx')

            # Check transaction is payment type. We don't accept other type in nobitex yet
            if tx_data.get('TransactionType').lower() != 'payment':
                # report_event('[RippleInspector:verify_transaction] Received transaction is not payment')
                return None

            tx_meta = tx.get('meta')

            # Check delivered amount dut to partial payment mechanism in ripple
            delivered_amount = tx_meta.get('delivered_amount')

            if not delivered_amount:
                # report_event('[RippleInspector:verify_transaction] Received transaction does not have delivered amount')
                return None
            if isinstance(delivered_amount, dict):
                # report_event('[RippleInspector:verify_transaction] Received transaction is not xrp transaction')
                return None

            # Check the tag address
            tag = tx.get('destination_tag')
            if not tag:
                # report_event('[RippleInspector:verify_transaction] Received transaction does not have destination tag')
                return None

            return Transaction(
                address=None,
                hash=tx.get('hash'),
                timestamp=parse_datetime(tx.get('date')),
                value=Decimal(delivered_amount),
                confirmations=0,
                is_double_spend=False,  # TODO check for double spend
                details=tx,
                tag=int(tag),
            )
        return None

    @classmethod
    def get_wallet_withdraws_ledger(cls, address):
        """
            This function returns only withdraws and only for xrp in its default network -XRP-
            and use https://data.ripple.com/ as its reference just as get wallet transactions
        """
        try:
            start_time = datetime.datetime.utcnow() - datetime.timedelta(days=1)
            explorer_url = cls.get_explorer_url() + 'v2/accounts/{}/payments?type=sent&currency=xrp&start={}&limit=700'
            api_response = cls.get_session().get(
                explorer_url.format(
                    address,
                    start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
                ),
                timeout=60,
            )
            api_response.raise_for_status()
            info = api_response.json()
        except Exception as e:
            print('Failed to get XRP wallet withdraws from API: {}'.format(str(e)))
            report_exception()
            return None
        if info.get('result') != "success":
            # report_event('Ripple API Result Error')
            return None
        txs = info.get('payments')
        if not txs:
            return []

        return cls.parse_payments(txs, address, return_withdraws=True)

    @classmethod
    def get_wallet_withdraws(cls, address):
        withdraws = cls.get_wallet_transactions_rpc(address).get(Currencies.xrp)
        start_time = pytz.timezone('UTC').localize(datetime.datetime.utcnow()) - datetime.timedelta(
            hours=3)  # now -3 hours , UTC base because api outputs are in UTC
        withdraws = [wtd for wtd in withdraws if wtd.timestamp > start_time and wtd.value < Decimal('0')]
        return withdraws
