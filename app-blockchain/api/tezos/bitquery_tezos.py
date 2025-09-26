import json
import datetime
import random
from typing import List
from decimal import Decimal
from django.conf import settings
from exchange.blockchain.utils import APIError
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class BitQueryTezosValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.01')

    @classmethod
    def validate_general_response(cls, response):
        if not response:
            return False
        if 'errors' in response:
            raise APIError('[BitQueryTezosAPI][ValidateGeneralResponse]' + response.get('errors')[0].get('message'))
        if not response.get('data'):
            return False
        if not response.get('data').get('tezos'):
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response) -> bool:
        if (cls.validate_general_response(balance_response)
                and balance_response.get('data').get('tezos').get('address')[0].get('balance')[0].get('available')):
            return True

    @classmethod
    def validate_block_head_response(cls, block_head_response) -> bool:
        if (cls.validate_general_response(block_head_response)
                and block_head_response.get('data').get('tezos').get('blocks')[0].get('count')):
            return True

    @classmethod
    def validate_tx_details_address_txs_response(cls, api_response) -> bool:
        if not cls.validate_general_response(api_response):
            return False
        response = api_response.get('data').get('tezos')
        if not response.get('transactions'):
            return False
        if not response.get('blocks') or not isinstance(response.get('blocks'), list):
            return False
        if not response.get('blocks')[0].get('count') or not isinstance(response.get('blocks')[0].get('count'), int):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        return cls.validate_tx_details_address_txs_response(tx_details_response)

    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        if any(transaction.get(field) is None for field in
               ('amount', 'hash', 'receiver', 'sender', 'timestamp', 'success', 'internal', 'status', 'block', 'fee')):
            return False
        if (Decimal(str(transaction.get('amount'))) < cls.min_valid_tx_amount
                or transaction.get('status') != 'applied'
                or not transaction.get('success')
                or transaction.get('internal')
                or (not isinstance(transaction.get('sender'), dict) or not transaction.get('sender').get('address'))
                or (not isinstance(transaction.get('receiver'), dict) or not transaction.get('receiver').get('address'))
                or transaction.get('sender').get('address') == transaction.get('receiver').get('address')):
            return False
        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response) -> bool:
        if (cls.validate_general_response(block_txs_response) and
                block_txs_response.get('data').get('tezos').get('transactions')):
            return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response) -> bool:
        return cls.validate_tx_details_address_txs_response(address_txs_response)

    @classmethod
    def validate_amount(cls, amount):
        if cls.min_valid_tx_amount < Decimal(str(amount)):
            return True
        return False

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response) -> bool:
        if not block_txs_raw_response or not isinstance(block_txs_raw_response, dict):
            return False
        if not block_txs_raw_response.get('data') or not isinstance(block_txs_raw_response.get('data'), dict):
            return False
        if (not block_txs_raw_response.get('data').get('tezos') or
                not isinstance(block_txs_raw_response.get('data').get('tezos'), dict)):
            return False
        if (not block_txs_raw_response.get('data').get('tezos').get('transactions') or
                not isinstance(block_txs_raw_response.get('data').get('tezos').get('transactions'), list)):
            return False
        return True


class BitQueryTezosParser(ResponseParser):
    validator = BitQueryTezosValidator
    currency = Currencies.xtz
    precision = 6
    symbol = 'XTZ'

    @classmethod
    def parse_balance_response(cls, balance_response) -> Decimal:
        if cls.validator.validate_balance_response(balance_response):
            return Decimal(
                str(balance_response.get('data').get('tezos').get('address')[0].get('balance')[0].get('available')))

    @classmethod
    def parse_block_head_response(cls, block_head_response):
        if cls.validator.validate_block_head_response(block_head_response):
            return int(block_head_response.get('data').get('tezos').get('blocks')[0].get('count'))

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response):
            transactions = tx_details_response.get('data').get('tezos').get('transactions')
            block_head = tx_details_response.get('data').get('tezos').get('blocks')[0].get('count')
            return [
                TransferTx(
                    block_height=int(transaction.get('block').get('height')),
                    block_hash=transaction.get('block').get('hash'),
                    tx_hash=transaction.get('hash'),
                    date=parse_iso_date(transaction.get('timestamp').get('time')),
                    success=True,
                    confirmations=block_head - int(transaction.get('block').get('height')),
                    from_address=transaction.get('sender').get('address'),
                    to_address=transaction.get('receiver').get('address'),
                    value=Decimal(str(transaction.get('amount'))),
                    symbol=cls.symbol,
                    memo=None,
                    tx_fee=Decimal(str(transaction.get('fee'))),
                    token=None,
                )
                for transaction in transactions
                if cls.validator.validate_transaction(transaction) and cls.validator.validate_amount(
                    transaction.get('amount'))
            ]

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        block_head = address_txs_response.get('data').get('tezos').get('blocks')[0].get('count')
        return [
            TransferTx(
                block_height=int(tx.get('block').get('height')),
                block_hash=tx.get('block').get('hash'),
                tx_hash=tx.get('hash'),
                date=parse_iso_date(tx.get('timestamp').get('time')),
                success=True,
                confirmations=block_head - int(tx.get('block').get('height')),
                from_address=tx.get('sender').get('address'),
                to_address=tx.get('receiver').get('address'),
                value=Decimal(str(tx.get('amount'))),
                symbol=cls.symbol,
                memo=None,
                tx_fee=Decimal(str(tx.get('fee'))),
                token=None,
            )
            for tx in address_txs_response.get('data').get('tezos').get('transactions')
            if cls.validator.validate_transaction(tx) and cls.validator.validate_amount(tx.get('amount'))
        ] if cls.validator.validate_address_txs_response(address_txs_response) else []

    @classmethod
    def parse_block_txs_response(cls, block_txs_response) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=int(tx.get('block').get('height')),
                block_hash=tx.get('block').get('hash'),
                tx_hash=tx.get('hash'),
                date=parse_iso_date(tx.get('timestamp').get('time')),
                success=True,
                confirmations=None,
                from_address=tx.get('sender').get('address'),
                to_address=tx.get('receiver').get('address'),
                value=Decimal(str(tx.get('amount'))),
                symbol=cls.symbol,
                memo=None,
                tx_fee=Decimal(str(tx.get('fee'))),
                token=None,
            )
            for tx in block_txs_response.get('data').get('tezos').get('transactions')
            if cls.validator.validate_transaction(tx)
        ] if cls.validator.validate_block_txs_response(block_txs_response) else []


class BitQueryTezosApi(GeneralApi):
    parser = BitQueryTezosParser
    need_block_head_for_confirmation = False
    symbol = 'XTZ'
    cache_key = 'xtz'
    _base_url = 'https://graphql.bitquery.io/'
    block_height_offset = 4
    supported_requests = {
        'get_balance': '',
        'get_tx_details': '',
        'get_block_head': '',
        'get_address_txs': '',
        'get_block_txs': ''
    }
    queries = {
        'get_balance': '''
            query get_balance($address: String) {
                tezos{
                    address(address: { is: $address}) {
                        balance{
                            available
                        }
                        address
                    }
                }
           }
        ''',
        'get_address_txs': '''
            query get_address_txs($address: String, $fromDate: ISO8601DateTime!) {
                tezos(network: tezos) {
                    blocks {
                        count
                    }
                    transactions(
                      receiver: {is: $address}
                      internal: {is: false}
                      success: {is: true}
                      destinationContract: {is: false}
                      time: {since: $fromDate}
                    ) 
                    {
                        hash
                        internal
                        sender {
                            address
                        }
                        receiver {
                            address
                        }
                        timestamp {
                            time(format: "%Y-%m-%dT%H:%M:%SZ")
                        }
                        block {
                            hash
                         height
                        }
                        amount
                        success
                        status
                        fee
                    }
                }
            }
        ''',
        'get_block_txs': '''
            query get_block_txs($block_height: BigInt) {
                tezos {
                    transactions(
                        block: {is: $block_height}
                        success: {is: true}
                        internal: {is: false}
                        destinationContract: {is: false}
                    )
                    {
                        hash
                        internal
                        sender {
                            address
                        }
                        receiver {
                            address
                        }
                        status
                        success
                        timestamp {
                            time(format: "%Y-%m-%dT%H:%M:%SZ")
                        }
                        block {
                            hash
                            height
                        }
                        amount
                        fee
                    }
                }
            }
        ''',
        'get_tx_details': '''
            query get_tx_details($hash: String) {
                tezos {
                    blocks {
                        count
                    }
                    transactions(
                        hash: {is: $hash},
                        success: {is: true},
                        internal: {is: false},
                        destinationContract: {is: false}
                    )
                    {
                        amount
                        hash
                        receiver {
                            address
                        }
                        status
                        timestamp {
                            time(format: "%Y-%m-%dT%H:%M:%SZ")
                        }
                        internal
                        sender {
                            address
                        }
                        block {
                            height
                            hash
                        }
                        success
                        fee
                    }
                }
            }
        ''',
        'get_block_head': '''        
            query block_head {
                tezos {
                    blocks {
                        count
                    }
                }
            }
        '''
    }

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.BITQUERY_API_KEY)

    @classmethod
    def get_headers(cls):
        header = {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.get_api_key()
        }
        return header

    @classmethod
    def get_balance_body(cls, address):
        data = {
            'query': cls.queries.get('get_balance'),
            'variables': {'address': address}
        }
        return json.dumps(data)

    @classmethod
    def get_block_head_body(cls):
        data = {
            'query': cls.queries.get('get_block_head')
        }
        return json.dumps(data)

    @classmethod
    def get_address_txs_body(cls, address):
        data = {
            'query': cls.queries.get('get_address_txs'),
            'variables': {
                'address': address,
                'fromDate': (datetime.datetime.now() - datetime.timedelta(days=3)).isoformat()
            }
        }
        return json.dumps(data)

    @classmethod
    def get_block_txs_body(cls, block_height):
        data = {
            'query': cls.queries.get('get_block_txs'),
            'variables': {'block_height': block_height}
        }
        return json.dumps(data)

    @classmethod
    def get_tx_details_body(cls, tx_hash):
        data = {
            'query': cls.queries.get('get_tx_details'),
            'variables': {'hash': tx_hash}
        }
        return json.dumps(data)
