import datetime
from decimal import Decimal

from django.utils.dateparse import parse_datetime

from exchange.base.logging import report_event
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class RippleAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: Ripple
    API docs: https://data.ripple.com
    """

    _base_url = 'https://data.ripple.com'
    testnet_url = 'http://testnet.data.api.ripple.com'
    symbol = 'XRP'

    active = True

    rate_limit = 0
    max_items_per_page = 1000
    page_offset_step = None
    confirmed_num = None
    PRECISION = 6
    XPUB_SUPPORT = False

    supported_requests = {
        'get_balance': '/v2/accounts/{address}/balances?currency=XRP',
        'get_transactions': '/v2/accounts/{address}/payments?type=received&currency=xrp&start={start_time}&limit=200',
        'get_tx_details': '/v2/transactions/{tx_hash}',
        'block_head': '/v2/health/importer?verbose=true',
    }

    def get_name(self):
        return 'ripple_api'

    def get_balance(self, address):
        self.validate_address(address)
        response = self.request('get_balance', address=address)
        if not response:
            raise APIError("[RippleAPI][Get Balance] response is None")
        balance = Decimal(response['balances'][0]['value'])
        return {
            'amount': balance,
        }

    def get_txs(self, address, offset=None, limit=None, unconfirmed=False, tx_direction_filter=''):
        self.validate_address(address)
        start_time = datetime.datetime.now() - datetime.timedelta(days=1)
        response = self.request('get_transactions', address=address, start_time=start_time.date())
        if not response:
            raise APIError("[RippleAPI][Get Transactions] response is None")

        if response.get('result') != "success":
            raise APIError("[RippleAPI][Get Transactions] unsuccessful")

        txs = response.get('payments')
        if not txs:
            return []
        transactions = []
        for tx in txs:
            parsed_tx = self.parse_tx(tx, address)
            if parsed_tx is not None:
                transactions.append(parsed_tx)

        return transactions

    def parse_tx(self, tx, address=None):
        delivered_amount = tx.get('delivered_amount')
        if not delivered_amount:
            return
        if isinstance(delivered_amount, dict):
            return
        tag = tx.get('destination_tag')
        if not tag:
            return
        if tx.get('issuer') and tx.get('issuer') != tx.get('source'):
            # report_event('[RippleAPI:parse_tx] Issuer does not equal to source')
            return

        if tx.get('currency') != "XRP":
            return
            # report_event('[RippleInspector:parse_payments] currency does not equal to xrp, currency: {}, '
            #              'source_currency: {}'.format(tx.get('currency'), tx.get('source_currency')))

        value = Decimal('0')
        if address:
            destination = tx.get('destination')
            source = tx.get('source')
            if source == address:
                value = -Decimal(delivered_amount)
            elif destination == address:
                value = Decimal(delivered_amount)

        return {
            'from_address': [tx.get('source')],
            'address': address,
            'hash': tx.get('tx_hash'),
            'date': parse_datetime(tx.get('executed_time')),
            'amount': value,
            'raw': tx,
            'memo': int(tag) if tag else None,
        }

    def get_tx_details(self, tx_hash):
        response = self.request('get_tx_details', tx_hash=tx_hash)
        if not response:
            raise APIError('Response is none')
        tx = self.parse_tx_details(response)
        response = self.request('block_head')
        tx['confirmations'] = response.get('last_validated_ledger') - tx.get('block')
        return tx

    def parse_tx_details(self, tx_info):
        transfers = []
        if tx_info.get('transaction', {}).get('tx', {}).get('TransactionType') == 'Payment':
            transfers.append({
                'from': tx_info.get('transaction').get('tx').get('Account'),
                'to': tx_info.get('transaction').get('tx').get('Destination'),
                'value': self.from_unit(int(tx_info.get('transaction').get('tx').get('Amount'))),
            })
        return {
            'hash': tx_info.get('transaction', {}).get('hash'),
            'success': tx_info.get('result') == 'success',
            'inputs': [],
            'outputs': [],
            'transfers': transfers,
            'block': tx_info.get('transaction', {}).get('ledger_index'),
            'fees': self.from_unit(int(tx_info.get('transaction', {}).get('tx', {}).get('Fee'))),
            'date': datetime.datetime.fromisoformat(tx_info.get('transaction', {}).get('date')),
            'raw': tx_info,
        }
