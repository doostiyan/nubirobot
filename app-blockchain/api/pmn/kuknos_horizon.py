import datetime
from decimal import Decimal

import base58
from django.utils.timezone import now

from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


def to_hex(address):
    return base58.b58decode_check(address).hex().upper()


def from_hex(address):
    return base58.b58encode_check(bytes.fromhex(address))


# weal API, low information to return
class KuknosHorizonAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: pmn
    API docs: https://horizon2.kuknos.org
    Explorer: Full Node
    :exception ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut
    """

    active = True

    symbol = 'XLM'
    currency_symbol = 'PMN'
    currency = Currencies.pmn
    _base_url = 'https://horizon.kuknos.org'
    testnet_url = 'https://hz2-test.kuknos.ir'
    rate_limit = 0
    PRECISION = 7
    max_items_per_page = 20  # 20 for get_txs
    page_offset_step = None
    confirmed_num = None

    USE_PROXY = False

    supported_requests = {
        'get_balance': '/accounts/{address}',
        'get_payments': '/accounts/{address}/payments?order=desc&limit={limit}',
        'get_txs': '/accounts/{address}/transactions?order=desc&limit={limit}',
        'get_tx_details': '/transactions/{hash}',
        'get_tx_payments': '/transactions/{hash}/payments',
    }

    def get_name(self):
        return 'horizon_api'

    def get_balance(self, address):
        self.validate_address(address)
        response = self.request('get_balance', address=address)
        if not response:
            raise APIError("[KuknosHorizonAPI][Get Balance] response is None")

        if response.get('account_id') != address:
            return None
        balance_list = response.get('balances')
        for balance_item in balance_list:
            if balance_item.get('asset_type') == 'native':
                balance = Decimal(balance_item.get('balance'))
                break
        else:
            return None

        # Ignore asset balance and trc20 balance other than USDT
        balances = {
            self.currency: {
                'symbol': self.currency_symbol,
                'amount': balance,
                'address': address
            }
        }

        return balances

    def get_tx_details(self, tx_hash):
        response = self.request('get_tx_details', hash=tx_hash)
        if not response:
            raise APIError('Response is none')
        payments = self.request('get_tx_payments', hash=tx_hash)
        if payments:
            response.update({
                'payments': payments.get('_embedded', {}).get('records', [])
            })
        tx = self.parse_tx_details(response)
        return tx

    def parse_tx_details(self, tx):
        transfers = []
        for payment in tx.get('payments'):
            if payment.get('type') == 'payment' and payment.get('type_i') == 1 \
                    and payment.get('transaction_successful') and payment.get('asset_type') == 'native':
                transfers.append({
                    'symbol': self.currency_symbol,
                    'currency': self.currency,
                    'from': payment.get('from'),
                    'to': payment.get('to'),
                    'token': '',
                    'name': '',
                    'value': Decimal(payment.get('amount'))
                })

        return {
            'hash': tx.get('hash'),
            'success': tx.get('successful'),
            'is_valid': True if transfers else False,
            'inputs': [],
            'outputs': [],
            'transfers': transfers,
            'memo': tx.get('memo') or '',
            'block': tx.get('ledger'),
            'confirmations': 0,
            'date': parse_iso_date(tx.get('created_at')),
        }

    def get_txs(self, address, offset=0, limit=20, tx_type='normal', unconfirmed=False):
        self.validate_address(address)
        txs = self._get_txs(address=address, offset=offset, limit=limit, unconfirmed=unconfirmed)
        memoes = self._get_memoes(address=address, offset=offset, limit=limit, unconfirmed=unconfirmed)

        result = []
        for tx in txs:
            parsed_tx = self.parse_tx(tx=tx, memoes=memoes, tx_type=tx_type, address=address)
            if parsed_tx is not None:
                result.append(parsed_tx)
        return result

    def _get_txs(self, address, offset=0, limit=20, unconfirmed=False):
        response = self.request('get_payments', address=address, limit=limit)
        if not response:
            raise APIError("[KuknosHorizonAPI][Get Transactions] response is None")
        payments = response.get('_embedded', {}).get('records')
        return payments

    def _get_memoes(self, address, offset=0, limit=20, unconfirmed=False):
        response = self.request('get_txs', address=address, limit=limit)
        if not response:
            raise APIError("[KuknosHorizonAPI][Get Transactions] response is None")
        transactions_memo = {}
        transactions = response.get('_embedded', {}).get('records')

        for tx in transactions:  # set transaction memo ->  tx_hash : memo
            tx_hash = tx.get('hash')
            if not tx_hash:
                continue
            if not tx.get('successful'):
                continue
            if tx.get('source_account') == address:
                continue
            transactions_memo[tx_hash] = tx.get('memo')

        return transactions_memo

    def parse_tx(self, tx, memoes, address, tx_type='normal'):
        if not tx.get('transaction_successful'):
            return None
        if tx.get('type_i') != 1 or tx.get('payment'):
            return None
        if tx.get('asset_type') != 'native':
            return None
        if tx.get('asset_issuer') or tx.get('asset_code'):
            return None
        if tx.get('source_account') != tx.get('from'):
            return None
        if tx.get('to') == address:
            direction = 'incoming'
        elif tx.get('from') == address:
            direction = 'outgoing'
        else:
            return None
        value = Decimal(tx.get('amount'))
        if not value or value <= Decimal(0):
            return None
        tx_hash = tx.get('transaction_hash')
        tx_timestamp = parse_iso_date(tx.get('created_at'))
        if tx_hash is None or tx_timestamp is None:
            return None
        tx_memo = memoes.get(tx_hash)
        if tx_memo is None or tx_memo == '':
            return None

        # ignore old transactions for change api
        ignore_before_date = now() - datetime.timedelta(days=1)
        if tx_timestamp < ignore_before_date:
            return None

        return {self.currency: {
            'symbol': self.currency_symbol,
            'date': tx_timestamp,
            'from_address': tx.get('from'),
            'to_address': tx.get('to'),
            'amount': value,
            'hash': tx_hash,
            'memo': tx_memo,
            'confirmations': 1,
            'confirmed': None,
            'type': tx_type,
            'kind': 'transaction',
            'direction': direction,
            'raw': tx,
        }}
