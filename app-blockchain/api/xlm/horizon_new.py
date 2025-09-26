import datetime
from typing import List
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator


class StellarHorizonValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0')

    @classmethod
    def validate_general_response(cls, response):
        if not response:
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response) -> bool:
        if not cls.validate_general_response(balance_response):
            return False
        if not balance_response.get('account_id'):
            return False
        if not balance_response.get('balances'):
            return False
        if not isinstance(balance_response['balances'], list):
            return False
        if not balance_response.get('balances')[0].get('asset_type'):
            return False
        if balance_response.get('balances')[0].get('asset_type') != 'native':
            return False
        if not balance_response.get('balances')[0].get('balance'):
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if not address_txs_response.get('pay_response'):
            return False
        if not address_txs_response.get('tx_response'):
            return False
        if not address_txs_response.get('pay_response').get('_embedded'):
            return False
        if not address_txs_response.get('tx_response').get('_embedded'):
            return False
        if not address_txs_response.get('pay_response').get('_embedded').get('records'):
            return False
        if not address_txs_response.get('tx_response').get('_embedded').get('records'):
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        key2check = ['hash', 'successful', 'source_account', 'ledger']
        for key in key2check:
            if not transaction.get(key):
                return False
        # Ignore transaction before the specific ledger number
        if transaction.get('ledger') <= 30224000:
            return False
        return True

    @classmethod
    def validate_pay_record(cls, record) -> bool:
        key2check = ['transaction_successful', 'type_i', 'asset_type', 'created_at', 'transaction_hash',
                     'source_account', 'from', 'to']
        for key in key2check:
            if not record.get(key):
                return False
        if record.get('type_i') != 1:
            return False
        if record.get('payment'):
            return False
        if record.get('asset_type') != 'native':
            return False
        if record.get('source_account') != record.get('from'):
            return False
        if Decimal(record.get('amount') or record.get('starting_balance') or '0') <= cls.min_valid_tx_amount:
            return False
        if parse_iso_date(record.get('created_at')) < timezone.now() - datetime.timedelta(days=1):
            return False
        return True


class StellarHorizonParser(ResponseParser):
    validator = StellarHorizonValidator
    precision = 7
    symbol = 'XLM'
    currency = Currencies.xlm

    @classmethod
    def parse_balance_response(cls, balance_response) -> Decimal:
        if not cls.validator.validate_balance_response(balance_response):
            return Decimal(0)
        return Decimal(balance_response['balances'][0].get('balance'))

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return []
        pay_records = address_txs_response.get('pay_response').get('_embedded').get('records')
        tx_records = address_txs_response.get('tx_response').get('_embedded').get('records')

        txs_memo = {}
        for tx in tx_records:
            if cls.validator.validate_transaction(tx):
                txs_memo.update({tx.get('hash'): tx.get('memo')})

        transfers: List[TransferTx] = []
        for record in pay_records:
            if cls.validator.validate_pay_record(record):

                if record.get('transaction_hash') and txs_memo.get(record.get('transaction_hash')):
                    tx_memo = txs_memo[record.get('transaction_hash')]
                else:
                    tx_memo = ''

                transfers.append(
                    TransferTx(
                        tx_hash=record.get('transaction_hash'),
                        success=True,
                        from_address=record.get('from'),
                        to_address=record.get('to'),
                        value=Decimal(record.get('amount') or record.get('starting_balance') or '0'),
                        symbol=cls.symbol,
                        confirmations=1,
                        block_height=None,
                        block_hash=None,
                        date=parse_iso_date(record.get('created_at')),
                        memo=tx_memo,
                        tx_fee=None,
                        token=None,
                    ))
        return transfers


class StellarHorizonAPI(GeneralApi):
    parser = StellarHorizonParser
    _base_url = 'https://horizon.stellar.org/'
    testnet_url = 'https://horizon-testnet.stellar.org/'
    symbol = 'XLM'
    cache_key = 'xlm'
    need_block_head_for_confirmation = False

    supported_requests = {
        'get_balance': 'accounts/{address}',
        'get_payments': 'accounts/{address}/payments?order=desc&limit=30',
        'get_address_txs': 'accounts/{address}/transactions?order=desc&limit=30'
    }

    @classmethod
    def get_header(cls):
        return {
            'User-Agent': (
                'Mozilla/5.0 (X11; Linux x86_64; rv:75.0) Gecko/20100101 Firefox/75.0' if not settings.IS_VIP else
                'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/109.0')
        }

    @classmethod
    def get_address_txs(cls, address, **kwargs):
        pay_response = cls.request('get_payments', address=address, headers=cls.get_header())
        tx_response = cls.request('get_address_txs', address=address)
        return {'pay_response': pay_response, 'tx_response': tx_response}
