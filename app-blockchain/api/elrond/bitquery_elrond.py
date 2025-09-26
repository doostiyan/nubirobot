import json
import random
import datetime
from _pydecimal import ROUND_DOWN
from decimal import Decimal
from typing import List

from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseValidator, ResponseParser


class BitqueryElrondValidator(ResponseValidator):
    success_status = 'success'
    valid_function = ''
    min_valid_tx_amount = Decimal(0)

    @classmethod
    def validate_general_response(cls, response):
        if response.get('data') is None:
            return False
        if response.get('data').get('elrond') is None:
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        blocks = block_head_response.get('data').get('elrond').get('blocks')
        if blocks is None or len(blocks) != 1:
            return False
        if blocks[0].get('height') is None:
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        transactions = tx_details_response.get('data').get('elrond').get('transactions')
        if transactions is None or len(transactions) != 1:
            return False
        return cls.validate_transaction(transactions[0])

    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        if transaction is None:
            return False
        if transaction.get('function') != cls.valid_function:
            return False
        if transaction.get('receiver').get('address') == transaction.get('sender').get('address'):
            return False
        if transaction.get('status') != cls.success_status:
            return False
        if Decimal(transaction.get('value')) <= cls.min_valid_tx_amount:
            return False
        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response):
        if not cls.validate_general_response(block_txs_response):
            return False
        transactions = block_txs_response.get('data').get('elrond').get('transactions')
        if transactions is None or len(transactions) == 0:
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        return True


class BitqueryElrondParser(ResponseParser):
    validator = BitqueryElrondValidator

    symbol = 'EGLD'
    currency = Currencies.egld
    average_block_time = 6

    @classmethod
    def parse_block_head_response(cls, block_head_response) -> int:
        if not cls.validator.validate_block_head_response(block_head_response):
            return 0
        return int(block_head_response.get('data').get('elrond').get('blocks')[0].get('height'))

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        if not cls.validator.validate_tx_details_response(tx_details_response):
            return None
        transaction = tx_details_response.get('data').get('elrond').get('transactions')[0]
        block = int(transaction.get('any')) if transaction.get('senderShard') == 1 else 0
        tx_date_time = datetime.datetime.strptime(transaction.get('time').get('time'), '%Y-%m-%d %H:%M:%S')
        confirmations = cls.calculate_tx_confirmations(tx_date_time)
        value = Decimal(str(transaction.get('value')))
        fees = Decimal(str(transaction.get('fee')))
        return [TransferTx(
            tx_hash=transaction.get('hash'),
            success=True,
            block_height=block,
            date=tx_date_time,
            confirmations=confirmations,
            symbol=cls.symbol,
            from_address=transaction.get('sender').get('address'),
            to_address=transaction.get('receiver').get('address'),
            value=value,
            tx_fee=fees,
            block_hash=transaction.get('senderBlock').get('hash'),
            memo=None,
            token=None
        )]

    @classmethod
    def parse_block_txs_response(cls, block_txs_response) -> List[TransferTx]:
        if not cls.validator.validate_block_txs_response(block_txs_response):
            return None
        block_txs = []
        for tx in block_txs_response.get('data').get('elrond').get('transactions'):
            if cls.validator.validate_transaction(tx):
                from_address = tx.get('sender').get('address')
                to_address = tx.get('receiver').get('address')
                tx_hash = tx.get('hash')
                block = int(tx.get('any')) if tx.get('senderShard') == 1 else 0
                value = Decimal(str(tx.get('value')))
                fees = Decimal(str(tx.get('fee')))
                tx_date_time = datetime.datetime.strptime(tx.get('time').get('time'), '%Y-%m-%d %H:%M:%S')
                confirmations = cls.calculate_tx_confirmations(tx_date_time)
                block_tx = TransferTx(
                    from_address=from_address,
                    to_address=to_address,
                    tx_hash=tx_hash,
                    symbol=cls.symbol,
                    value=value,
                    block_hash=tx.get('senderBlock').get('hash'),
                    date=tx_date_time,
                    confirmations=confirmations,
                    tx_fee=fees,
                    success=True,
                    block_height=block,
                    memo=None
                )
                block_txs.append(block_tx)
        return block_txs

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return None
        address_txs: List[TransferTx] = []
        for tx in address_txs_response.get('data').get('elrond').get('transactions'):
            if cls.validator.validate_transaction(tx):
                block = int(tx.get('any')) if tx.get('senderShard') == 1 else 0
                tx_date_time = datetime.datetime.strptime(tx.get('time').get('time'), '%Y-%m-%d %H:%M:%S')
                confirmations = cls.calculate_tx_confirmations(tx_date_time)
                value = Decimal(str(tx.get('value')))
                fees = Decimal(str(tx.get('fee')))
                address_tx = TransferTx(
                    tx_hash=tx.get('hash'),
                    from_address=tx.get('sender').get('address'),
                    to_address=tx.get('receiver').get('address'),
                    value=value,
                    block_height=block,
                    date=tx_date_time,
                    confirmations=confirmations,
                    block_hash=tx.get('senderBlock').get('hash'),
                    success=True,
                    symbol=cls.symbol,
                    tx_fee=fees,
                    memo=None
                )
                address_txs.append(address_tx)
        return address_txs

    @classmethod
    def calculate_tx_confirmations(cls, tx_date):
        current_date_time = datetime.datetime.now(datetime.timezone.utc)
        current_date_time = current_date_time.replace(tzinfo=None)
        diff = (current_date_time - tx_date).total_seconds()
        return int(diff / cls.average_block_time)


class BitqueryElrondApi(GeneralApi):
    parser = BitqueryElrondParser
    cache_key = 'egld'

    _base_url = 'https://graphql.bitquery.io'
    supported_requests = {
        'get_address_txs': '',
        'get_block_txs': '',
        'get_block_head': '',
        'get_tx_details': ''
    }

    shard_number = 1
    queries = {
        'get_address_txs': '''
            query address_txs($limit: Int!, $address: String) {
                elrond {
                    transactions(
                        txReceiver: {is: $address}
                        options: {limit: $limit, desc: "time.time"}
                        function: {is: ""}
                        status: {is: "success"}
                    ) {
                        time {
                            time(format: "%Y-%m-%d %H:%M:%S")
                        }
                        hash
                        status
                        any(of: height)
                        receiver {
                            address
                        }
                        sender {
                            address
                        }
                        value
                        fee
                        senderShard
                        function
                        senderBlock {
                            hash
                        }
                    }
                }
            }
        ''',
        'get_tx_details': '''
            query tx_details($tx_hash: String) {
                elrond {
                    transactions(
                        txHash: {is: $tx_hash}
                        function: {is: ""}
                        status: {is: "success"}
                    ) {
                        any(of: height)
                        sender {
                            address
                        }
                        receiver {
                            address
                        }
                        status
                        value
                        hash
                        fee
                        function
                        time {
                            time(format: "%Y-%m-%d %H:%M:%S")
                        }
                        senderShard
                        senderBlock {
                            hash
                        }
                    }
                }
            }
        ''',
        'get_block_txs': '''
            query block_txs($shard: BigInt!, $height: Int!, $limit: Int!) {
                elrond {
                    transactions(
                        height: {is: $height}
                        shard: {is: $shard}
                        options: {limit: $limit}
                        function: {is: ""}
                        status: {is: "success"}
                    ) {
                        value
                        status
                        fee
                        sender {
                            address
                        }
                        receiver {
                            address
                        }
                        any(of: height)
                        time {
                            time(format: "%Y-%m-%d %H:%M:%S")
                        }
                        hash
                        function
                        senderBlock {
                            hash
                        }
                    }
                }
            }
        ''',
        'get_block_head': '''
            query block_head {
                elrond {
                    blocks(options: {desc: "time.time", limit: 1}, shard: {is: "1"}) {
                        time {
                            time(format: "%Y-%m-%d %H:%M:%S")
                        }
                        height
                    }
                }
            }
        '''
    }

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.ELROND_BITQUERY_API_KEY)

    @classmethod
    def get_headers(cls):
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.get_api_key()
        }

    @classmethod
    def get_tx_details_body(cls, tx_hash):
        data = {
            'query': cls.queries.get('get_tx_details'),
            'variables': {
                'tx_hash': tx_hash
            }
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
                'limit': cls.TRANSACTIONS_LIMIT,
                'address': address
            }
        }
        return json.dumps(data)

    @classmethod
    def get_block_txs_body(cls, block_height):
        data = {
            'query': cls.queries.get('get_block_txs'),
            'variables': {
                'height': block_height,
                'shard': cls.shard_number,
                'limit': cls.TRANSACTIONS_LIMIT
            }
        }
        return json.dumps(data)
