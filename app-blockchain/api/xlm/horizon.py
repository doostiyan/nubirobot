import datetime
from decimal import Decimal

import requests
from django.conf import settings
from django.utils.timezone import now

from exchange.base.logging import report_event
from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError


class XLMHorizonAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: XLM(stellar)

    API Docs(not only stellar):
        https://blockchair.com/api/docs#link_M2
        https://www.stellar.org/developers/reference/

    Get XLM transactions from https://horizon.stellar.org/
    """
    _base_url = 'https://horizon.stellar.org/'
    testnet_url = 'https://horizon-testnet.stellar.org/'
    symbol = 'XLM'
    currency = Currencies.xlm
    active = True
    api_sessions = {}
    PRECISION = 7
    USE_PROXY = False


    supported_requests = {
        'get_balance': 'accounts/{address}',
        'get_payments': 'accounts/{address}/payments?order=desc&limit=30',
        'get_txs': 'accounts/{address}/transactions?order=desc&limit=30'
    }

    def get_header(self):
        return {
            'User-Agent': (
                    'Mozilla/5.0 (X11; Linux x86_64; rv:75.0) Gecko/20100101 Firefox/75.0' if not settings.IS_VIP else
                    'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/109.0')
        }

    def get_balance(self, address):
        try:
            response = self.request('get_balance', address=address, headers=self.get_header())
        except Exception as e:
            print('Failed to get XLM wallet balance from API: {}'.format(str(e)))
            # report_event('StellarOrg API Error')
            return None
        if response.get('account_id') != address:
            return None
        balance_list = response.get('balances')
        if not balance_list or balance_list[0].get('asset_type') != 'native':
            return None
        balance = Decimal(balance_list[0].get('balance'))
        if balance is None:
            return None
        return {
            'address': address,
            'received': balance,
            'sent': Decimal('0'),
            'balance': balance,
            'unconfirmed': Decimal('0'),
        }

    def get_txs(self, address, tx_direction_filter='incoming', limit=25):
        try:
            # get payment
            pay_response = self.request('get_payments', address=address, headers=self.get_header())
            tx_response = self.request('get_txs', address=address)
        except Exception:
            raise APIError(f'{self.symbol} [XLMBlockchairAPI]: Failed to get txs, connection error')
        pay_records = pay_response.get('_embedded', {}).get('records')
        tx_records = tx_response.get('_embedded', {}).get('records')
        if not pay_records or not tx_records:
            return []
        if not address:
            return []
        transactions = self.parse_actions_horizon(pay_records, tx_records, address, tx_direction_filter)
        return transactions

    def parse_actions_horizon(self, pay_records, tx_records, address, tx_direction_filter):
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
            if tx_direction_filter == 'incoming':
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
                if tx_direction_filter == 'incoming':  # cause this check is only for deposits
                    continue
            if record.get('asset_type') != 'native':
                if tx_direction_filter == 'incoming':  # cause this check is only for deposits
                    continue
            if record.get('asset_issuer') or record.get('asset_code'):
                continue
            if record.get('source_account') != record.get('from'):
                if tx_direction_filter == 'incoming':  # cause this check is only for deposits
                    continue
            if tx_direction_filter == 'incoming':
                if address and record.get('to') != address:
                    continue

            if tx_direction_filter == 'incoming':
                value = Decimal(record.get('amount'))
            else:
                value = record.get('amount') or record.get('starting_balance') or '0'
                value = Decimal(value)

            if not value or value <= Decimal(0):
                continue
            if tx_direction_filter == 'outgoing':
                if address not in [record.get('source_account'), record.get('from')]:
                    continue
                value *= -1

            tx_hash = record.get('transaction_hash')
            tx_timestamp = parse_iso_date(record.get('created_at'))
            if tx_hash is None or tx_timestamp is None:
                continue
            tx_memo = transactions_memo.get(tx_hash)
            if tx_memo is None or tx_memo == '':  # without tag deposit is not okay but withdraw is
                if tx_direction_filter == 'incoming':
                    continue

            # ignore old transactions for change api
            ignore_before_date = now() - datetime.timedelta(days=1)
            if tx_timestamp < ignore_before_date:
                continue
            transactions.append({
                self.currency: {
                    'from_address': [record.get('from')],
                    'date': tx_timestamp,
                    'amount': value,
                    'hash': tx_hash,
                    'confirmations': 1,
                    'memo': tx_memo,
                    'raw': record,
                }})
        return transactions

