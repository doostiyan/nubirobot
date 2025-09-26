import datetime
import json
import random
from decimal import Decimal
from typing import Dict, List, Optional

from django.conf import settings

from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_iso_date
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
    from exchange.base.parsers import parse_iso_date

from exchange.blockchain.api.general.dtos.dtos import TransferTx


class FilecoinBitqueryValidator(ResponseValidator):
    successful_code = 'successful'
    valid_operation = 'transfer'
    success_status = 'success'

    @classmethod
    def validate_general_response(cls, response: Dict[str, any]) -> bool:
        if not response:
            return False
        if not response.get('data'):
            return False
        if not response.get('data').get('filecoin'):
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(balance_response):
            return False
        address_response = balance_response.get('data').get('filecoin').get('address')
        if not address_response:
            return False
        if not address_response[0].get('address') or type(address_response[0].get('address')) is not str:
            return False
        if not address_response[0].get('balance'):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        blocks_response = block_head_response.get('data').get('filecoin').get('blocks')
        if not blocks_response:
            return False
        if not blocks_response[0].get('height') or type(blocks_response[0].get('height')) is not int:
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        messages_response = tx_details_response.get('data').get('filecoin').get('messages')
        blocks_response = tx_details_response.get('data').get('filecoin').get('blocks')
        if not messages_response:
            return False
        if not messages_response[0]:
            return False
        if not isinstance(blocks_response, list) or not isinstance(blocks_response[0], dict):
            return False
        if not blocks_response[0].get('height') or not isinstance(blocks_response[0].get('height'), int):
            return False
        if not cls.validate_transaction(messages_response[0]):
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, any]) -> bool:
        if not transaction.get('hash'):
            return False
        if transaction.get('exitCode') != '0':
            return False
        if Decimal(str(transaction.get('amount'))) <= cls.min_valid_tx_amount:
            return False
        if transaction.get('method').get('name').casefold() != 'Transfer'.casefold():
            return False
        if transaction.get('sender').get('address') == transaction.get('receiver').get('address'):
            return False
        if not transaction.get('success'):
            return False
        return True

    @classmethod
    def validate_batch_block_txs_response(cls, batch_block_txs_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(batch_block_txs_response):
            return False
        blocks_response = batch_block_txs_response.get('data').get('filecoin').get('blocks')
        messages_response = batch_block_txs_response.get('data').get('filecoin').get('messages')
        if not blocks_response or not isinstance(blocks_response, list):
            return False
        if not blocks_response[0].get('height') or not isinstance(
                blocks_response[0].get('height'), int):
            return False
        if not messages_response or not isinstance(messages_response, list):
            return False
        return True

    @classmethod
    def validate_block_tx_transaction(cls, transaction: Dict[str, any]) -> bool:
        if not any(transaction.get(field) for field in
                   ['hash', 'method', 'any', 'receiver', 'sender', 'success', 'block', 'baseFeeBurn', 'minerTip',
                    'exitCode']):
            return False
        if not transaction.get('method').get('id') or transaction.get('method').get('id') != '0':
            return False
        if not transaction.get('method').get('name') or transaction.get('method').get(
                'name').casefold() != 'Transfer'.casefold():
            return False
        if transaction.get('receiver').get('address') == transaction.get('sender').get('address'):
            return False
        if not transaction.get('block').get('height') or not isinstance(transaction.get('block').get('height'), int):
            return False
        if transaction.get('exitCode') != '0':
            return False
        if not transaction.get('success'):
            return False
        if Decimal(str(transaction.get('any'))) <= cls.min_valid_tx_amount:
            return False
        return True


class FilecoinBitqueryParser(ResponseParser):
    validator = FilecoinBitqueryValidator
    symbol = 'FIL'
    currency = Currencies.fil
    precision = 18
    rate_limit = 0.33  # 3 req per sec

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, any]) -> Decimal:
        if cls.validator.validate_balance_response(balance_response):
            return Decimal(str(balance_response.get('data').get('filecoin').get('address')[0].get('balance')))
        return Decimal(0)

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, any]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return block_head_response.get('data').get('filecoin').get('blocks')[0].get('height')
        return None

    @classmethod
    def calculate_fee(cls, transfer: Dict[str, any]) -> Decimal:
        miner_tip = transfer.get('minerTip')
        base_fee_burn = transfer.get('baseFeeBurn')
        fee = miner_tip + base_fee_burn
        return Decimal(str(fee))

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, any], _: Optional[int]) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response):
            transaction = tx_details_response.get('data').get('filecoin').get('messages')[0]
            value = Decimal(str(transaction.get('amount')))
            fees = cls.calculate_fee(transaction)
            block = transaction.get('block').get('height')
            block_head = tx_details_response.get('data').get('filecoin').get('blocks')[0].get('height')
            confirmations = block_head - block + 1
            return [TransferTx(
                tx_hash=transaction.get('hash'),
                success=True,
                block_height=block,
                date=parse_iso_date(f"{transaction.get('date').get('date').replace(' ', 'T')}Z"),
                memo=None,
                symbol=cls.symbol,
                from_address=transaction.get('sender').get('address'),
                to_address=transaction.get('receiver').get('address'),
                token=None,
                block_hash=None,
                value=value,
                tx_fee=fees,
                confirmations=confirmations
            )]
        return []

    @classmethod
    def parse_batch_block_txs_response(cls, batch_block_txs_response: Dict[str, any]) -> List[TransferTx]:
        block_txs: List[TransferTx] = []
        if cls.validator.validate_batch_block_txs_response(batch_block_txs_response):
            transactions = batch_block_txs_response.get('data').get('filecoin').get('messages')
            block_head = batch_block_txs_response.get('data').get('filecoin').get('blocks')[0].get('height')
            for transaction in transactions:
                if cls.validator.validate_block_tx_transaction(transaction):
                    tx_hash = transaction.get('hash')
                    from_address = transaction.get('sender').get('address')
                    to_address = transaction.get('receiver').get('address')
                    block_height = transaction.get('block').get('height')
                    confirmations = block_head - block_height
                    date = parse_iso_date(transaction.get('block').get('timestamp').get('iso8601'))
                    fee = cls.calculate_fee(transaction)
                    value = Decimal(transaction.get('any'))
                    block_tx = TransferTx(
                        tx_hash=tx_hash,
                        from_address=from_address,
                        to_address=to_address,
                        block_height=block_height,
                        confirmations=confirmations,
                        date=date,
                        tx_fee=fee,
                        value=value,
                        success=True,
                        symbol=cls.symbol
                    )
                    block_txs.append(block_tx)
        return block_txs


class FilecoinBitqueryApi(GeneralApi):
    """
    coins: Filecoin
    API docs: https://graphql.bitquery.io/ide
    Explorer: https://explorer.bitquery.io/filecoin
    """
    _base_url = 'https://graphql.bitquery.io'
    cache_key = 'fil'
    PAGINATION_LIMIT = 25
    PAGINATION_OFFSET = 0
    PAGINATION_PAGE = 1
    parser = FilecoinBitqueryParser
    need_block_head_for_confirmation = False
    SUPPORT_BATCH_GET_BLOCKS = True

    supported_requests = {
        'get_balance': '',
        'get_block_head': '',
        'get_tx_details': '',
        'get_blocks_txs': ''
    }

    queries = {
        'get_balance': """
                query get_balance($address : String){
                    filecoin(network: filecoin) {
                        address(address: {is: $address}) {
                            balance
                            address
                        }
                    }
                }
            """,
        'get_block_head': """
                query get_block_head($limit: Int!, $offset: Int!, $toDate: ISO8601DateTime!) {
                    filecoin(network: filecoin) {
                        blocks(options: {limit: $limit, offset: $offset, desc: "height"}, date: {is: $toDate}) {
                            height
                        }
                    }
                }
            """,
        'get_tx_details': """
                query get_tx_details($hash: String, $toDate: ISO8601DateTime!) {
                    filecoin(network: filecoin) {
                        blocks(options: {limit: 1, offset: 0, desc: "height"}, date: {is: $toDate}) {
                                height
                        }
                        messages(hash: {is: $hash}, method: {is: 0}, success: true) {
                            method {
                                name
                            }
                            block {
                                height
                            }
                            hash
                            success
                            date {
                                    date(format: "%Y-%m-%d %H:%M:%S")
                            }
                            sender {
                                address
                            }
                            receiver {
                                address
                            }
                            gas
                            minerTip
                            baseFeeBurn
                            amount
                            exitCode
                        }
                    }
                }
             """,
        'get_blocks_txs':
            """
                query get_blocks_txs($fromBlock: Int!, $toBlock: Int!, $fromDate: ISO8601DateTime!, $toDate: ISO8601DateTime!) {
                    filecoin(network: filecoin) {
                        blocks(options: {limit: 1, offset: 0, desc: "height"}, date: {is: $toDate}) {
                            height
                        }
                        messages(
                            height: {between: [$fromBlock, $toBlock]}
                            method: {is: 0}
                            date: {between: [$fromDate, $toDate]}
                            options: {desc: "block.height"}
                            success: true
                        )
                        {
                            hash
                            method {
                                id
                                name
                            }
                            any(of: amount)
                            receiver {
                                address
                            }
                            sender {
                                address
                            }
                            success
                            block {
                                height
                                timestamp {
                                  iso8601
                                }
                            }
                            baseFeeBurn
                            minerTip
                            exitCode
                        }
                    }
                }
            """  # noqa: E501

    }

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.LTC_BITQUERY_API_KEY)

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.get_api_key()
        }

    @classmethod
    def get_block_head_body(cls) -> str:
        data = {
            'query': cls.queries.get('get_block_head'),
            'variables': {
                'limit': 1,
                'offset': 0,
                'toDate': datetime.datetime.utcnow().strftime('%Y-%m-%d')
            }
        }
        return json.dumps(data)

    @classmethod
    def get_balance_body(cls, address: str) -> str:
        data = {
            'query': cls.queries.get('get_balance'),
            'variables': {
                'address': address
            }

        }
        return json.dumps(data)

    @classmethod
    def get_tx_details_body(cls, tx_hash: str) -> str:
        data = {
            'query': cls.queries.get('get_tx_details'),
            'variables': {
                'hash': tx_hash,
                'toDate': datetime.datetime.utcnow().strftime('%Y-%m-%d')

            }
        }
        return json.dumps(data)

    @classmethod
    def get_blocks_txs_body(cls, from_block: int, to_block: int) -> str:
        now_date = datetime.datetime.utcnow()
        data = {
            'query': cls.queries.get('get_blocks_txs'),
            'variables': {
                'fromBlock': from_block,
                'toBlock': to_block,
                'toDate': now_date.strftime('%Y-%m-%d'),
                'fromDate': (now_date - datetime.timedelta(days=3)).strftime('%Y-%m-%d')
            }
        }
        return json.dumps(data)
