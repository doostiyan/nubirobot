import datetime
import time
from decimal import Decimal

from django.conf import settings
from django.utils.timezone import now
from exchange.base.logging import log_event, report_event, report_exception
from exchange.base.parsers import parse_iso_date, parse_utc_timestamp

from .models import BaseBlockchainInspector, Transaction


class XLMBlockchainInspector(BaseBlockchainInspector):
    """ Notify: api.stellar.expert does'nt return transaction's hash and returns id.
                horizon.stellar.org return transaction hash
    """
    USE_PROXY = False if not settings.IS_VIP else False
    TESTNET_ENABLED = False
    USE_HORIZON = True
    FAKE_USER_AGENT = True
    fail_count = 0

    get_balance_method = {
        'XLM': 'get_wallets_balance_xlm',
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
        if cls.USE_HORIZON:
            if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
                explorer_url = 'https://horizon-testnet.stellar.org/'
            else:
                explorer_url = 'https://horizon.stellar.org/'
        else:
            if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
                explorer_url = 'https://api.stellar.expert/explorer/testnet/'
            else:
                explorer_url = 'https://api.stellar.expert/explorer/public/'
        return explorer_url

    @classmethod
    def get_wallets_balance_xlm(cls, address_list):
        return cls.get_wallets_balance_from_horizon(address_list)

    @classmethod
    def get_wallets_balance_from_horizon(cls, address_list, raise_error=False):
        """ Get XLM account balance from https://horizon.stellar.org/
            API Document: https://www.stellar.org/developers/reference/
        """
        time.sleep(1)
        balances = []
        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            explorer_url = 'https://horizon-testnet.stellar.org/'
        else:
            explorer_url = 'https://horizon.stellar.org/'
        explorer_url += 'accounts/{}'
        for address in address_list:
            try:
                api_response = cls.get_session().get(explorer_url.format(address), timeout=30)
                api_response.raise_for_status()
                info = api_response.json()
            except Exception as e:
                if raise_error:
                    raise e
                print('Failed to get XLM wallet balance from API: {}'.format(str(e)))
                # report_event('StellarOrg API Error')
                return None
            if info.get('account_id') != address:
                continue
            balance_list = info.get('balances')
            if not balance_list or balance_list[0].get('asset_type') != 'native':
                continue
            balance = Decimal(balance_list[0].get('balance'))
            if balance is None:
                continue
            balances.append({
                'address': address,
                'received': balance,
                'sent': Decimal('0'),
                'balance': balance,
                'unconfirmed': Decimal('0'),
            })
        return balances

    @classmethod
    def get_wallet_transactions(cls, address, network=None):
        return cls.get_wallet_transactions_from_horizon(address)
        # Try twice in getting error
        # for i in range(0, 1):
        #     transactions = cls.get_transaction(address)
        #     if transactions is None:
        #         cls.fail_count += 1
        #     else:
        #         cls.fail_count = max(0, cls.fail_count - 1)
        #     if cls.fail_count >= 4:
        #         cls.USE_HORIZON = not cls.USE_HORIZON
        #         continue
        #     return transactions
        # return None

    # @classmethod
    # def get_transaction(cls, address):
    # if cls.USE_HORIZON:
    #     return cls.get_wallet_transactions_from_horizon(address)
    # else:
    #     return cls.get_wallet_transactions_from_expert(address)

    @classmethod
    def get_wallet_transactions_from_horizon(cls, address=None, raise_error=False):
        """ Get XLM transactions from https://horizon.stellar.org/
            API Document: https://www.stellar.org/developers/reference/
        """

        pay_explorer_url = cls.get_explorer_url() + 'accounts/{}/payments?order=desc&limit=30'.format(address)
        tx_explorer_url = cls.get_explorer_url() + 'accounts/{}/transactions?order=desc&limit=30'.format(address)
        try:
            # get payment
            pay_response = cls.get_session().get(pay_explorer_url, timeout=60)
            pay_response.raise_for_status()
            payments_info = pay_response.json()

            # get transactions
            tx_response = cls.get_session().get(tx_explorer_url, timeout=60)
            tx_response.raise_for_status()
            transactions_info = tx_response.json()
        except Exception as e:
            if raise_error:
                raise e
            print('Failed to get XLM wallet transactions from horizon API: {}'.format(str(e)))
            report_exception()
            return None

        pay_records = payments_info.get('_embedded', {}).get('records')
        tx_records = transactions_info.get('_embedded', {}).get('records')
        if not pay_records or not tx_records:
            return []
        if not address:
            return []
        transactions = cls.parse_actions_horizon(pay_records, tx_records, address)
        return transactions

    @classmethod
    def parse_actions_horizon(cls, pay_records, tx_records, address, return_withdraws=False):
        """
            params: return_withdraws = False means to this method to skip withdraws which is necessary in most cases
            do not change the default value pass it as True if U want to use it.
        """
        transactions = []
        transactions_memo = {}
        for tx in tx_records:  # set transaction memo ->  tx_hash : memo
            tx_hash = tx.get('hash')
            if not tx_hash:
                continue
            if not tx.get('successful'):
                continue
            if not return_withdraws:
                if address and tx.get('source_account') == address:
                    continue
            # Ignore transaction before the specific ledger number
            if tx.get('ledger') <= 30224000:
                continue
            transactions_memo[tx_hash] = tx.get('memo')

        # general checks
        for record in pay_records:
            if not record.get('transaction_successful'):
                continue
            if record.get('type_i') != 1 or record.get('payment'):
                if not return_withdraws:  # cause this check is only for deposits
                    continue
            if record.get('asset_type') != 'native':
                if not return_withdraws:  # cause this check is only for deposits
                    continue
            if record.get('asset_issuer') or record.get('asset_code'):
                continue
            if record.get('source_account') != record.get('from'):
                if not return_withdraws:  # cause this check is only for deposits
                    continue
            if not return_withdraws:
                if address and record.get('to') != address:
                    continue

            if not return_withdraws:
                value = Decimal(record.get('amount'))
            else:
                value = record.get('amount') or record.get('starting_balance') or '0'
                value = Decimal(value)

            if not value or value <= Decimal(0):
                continue
            if return_withdraws:
                if address not in [record.get('source_account'), record.get('from')]:
                    continue
                value *= -1

            tx_hash = record.get('transaction_hash')
            tx_timestamp = parse_iso_date(record.get('created_at'))
            if tx_hash is None or tx_timestamp is None:
                continue
            tx_memo = transactions_memo.get(tx_hash)
            if tx_memo is None or tx_memo == '':  # without tag deposit is not okay but withdraw is
                if not return_withdraws:
                    continue

            # ignore old transactions for change api
            ignore_before_date = now() - datetime.timedelta(days=1)
            if tx_timestamp < ignore_before_date:
                continue
            transactions.append(Transaction(
                address=address,
                from_address=[record.get('from')],
                hash=tx_hash,
                timestamp=tx_timestamp,
                value=value,
                confirmations=1,
                is_double_spend=False,
                details=record,
                tag=tx_memo,
            ))
        return transactions

    @classmethod
    def get_wallet_transactions_from_expert(cls, address, raise_error=False):
        """ Get XLM transactions from https://api.stellar.expert/
            API Document: https://github.com/orbitlens/stellar-expert-explorer/tree/master/docs/api
        """

        time.sleep(1)
        explorer_url = cls.get_explorer_url() + 'account/{}/history/payments?order=desc&limit=20'.format(address)
        try:
            api_response = cls.get_session().get(explorer_url, timeout=60)
            api_response.raise_for_status()
            info = api_response.json()
        except Exception as e:
            if raise_error:
                raise e
            print('Failed to get XLM wallet transactions from API: {}'.format(str(e)))
            return None
        records = info.get('_embedded', {}).get('records')
        if not records:
            return []
        if not address:
            return []
        transactions = cls.parse_records_expert(records, address)
        return transactions

    @classmethod
    def parse_records_expert(cls, records, address=None):
        transactions = []
        for record in records:
            if record.get('assets') != ['XLM']:
                continue
            if record.get('type') != 1:
                continue
            accounts = record.get('accounts')
            if not accounts or len(accounts) != 2:
                continue
            if address and (accounts[0] == address or accounts[1] != address):
                continue

            value = Decimal(record.get('amount'))
            if not value or value <= 0:
                continue

            tx_memo = record.get('memo')
            if tx_memo is None or tx_memo == '':
                continue
            transactions.append(Transaction(
                address=address,
                from_address=[accounts[0]],
                hash=record.get('tx'),
                timestamp=parse_utc_timestamp(record.get('ts')),
                value=value,
                confirmations=1,
                is_double_spend=False,
                details=record,
                tag=tx_memo,
            ))
        return transactions

    @classmethod
    def get_wallet_withdraws(cls, address):
        """
            This function is the same as get_wallet_transactions except it does care just about withdraw transactions.
            explorer_url and all other things are the same except calling parse_actions_horizon (to make it not to
            skip withdraws which happens by default)
            Note: this function only works for xlm in its own network -XLM-
        """
        pay_explorer_url = cls.get_explorer_url() + 'accounts/{}/payments?order=desc&limit=30'.format(address)
        tx_explorer_url = cls.get_explorer_url() + 'accounts/{}/transactions?order=desc&limit=30'.format(address)
        try:
            # get payment
            pay_response = cls.get_session().get(pay_explorer_url, timeout=60)
            pay_response.raise_for_status()
            payments_info = pay_response.json()

            # get transactions
            tx_response = cls.get_session().get(tx_explorer_url, timeout=60)
            tx_response.raise_for_status()
            transactions_info = tx_response.json()
        except Exception as e:
            print('Failed to get XLM wallet withdraws from horizon API: {}'.format(str(e)))
            report_exception()
            return None

        pay_records = payments_info.get('_embedded', {}).get('records')
        tx_records = transactions_info.get('_embedded', {}).get('records')
        if not pay_records or not tx_records:
            return []
        if not address:
            return []
        all_txs = cls.parse_actions_horizon(pay_records, tx_records, address, return_withdraws=True)
        withdraws = list(filter(lambda tx: tx.value < Decimal('0'), all_txs))
        return withdraws
