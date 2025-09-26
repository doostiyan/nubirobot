import json
from decimal import Decimal
from typing import List, Dict, Optional

from django.conf import settings

from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class FTMGraphqlResponseValidator(ResponseValidator):
    precision = 18

    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        if transaction is None:
            return False
        if not transaction.get('from') or not transaction.get('to'):
            return False
        if transaction.get('from') == transaction.get('to'):
            return False
        if transaction.get('from') in cls.invalid_from_addresses_for_ETH_like:
            return False
        if not transaction.get('hash') or not isinstance(transaction.get('hash'), str):
            return False
        if not transaction.get('value') or not isinstance(transaction.get('value'), str):
            return False
        if BlockchainUtilsMixin.from_unit(int(transaction.get('value'), 0), cls.precision) <= cls.min_valid_tx_amount:
            return False
        if transaction.get('status') != '0x1':
            return False
        if transaction.get('blockNumber') is None or not isinstance(transaction.get('blockNumber'), str):
            return False
        if transaction.get('block') is None or not isinstance(transaction.get('block'), Dict):
            return False
        if transaction.get('inputData') != '0x':
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if (account := address_txs_response.get('data').get('account')) is None or not isinstance(account, Dict):
            return False
        if (txs := account.get('txList')) is None or not isinstance(txs, Dict):
            return False
        if txs.get('edges') is None or not isinstance(txs.get('edges'), List):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        if not (block := block_head_response.get('data').get('block')) and not isinstance(block, Dict):
            return False
        if not block.get('number') or not isinstance(block.get('number'), str):
            return False
        return True

    @classmethod
    def validate_general_response(cls, response) -> bool:
        return (
                response is not None and
                isinstance(response, Dict) and
                response.get('errors') is None and
                response.get('data') is not None
        )

    @classmethod
    def validate_batch_block_txs_response(cls, batch_block_txs_response) -> bool:
        if not cls.validate_general_response(batch_block_txs_response):
            return False

        if (blocks := batch_block_txs_response.get('data').get('blocks')) is None:
            return False

        if (edges := blocks.get('edges')) is None:
            return False

        for edge in edges:
            if (block := edge.get('block')) is None:
                return False
            if block.get('txList') is None:
                return False

        return True

    @classmethod
    def validate_balance_response(cls, balance_response) -> bool:
        if (account := balance_response.get('data').get('account')) is None:
            return False

        if account.get('balance') is None:
            return False

        return True

    @classmethod
    def validate_token_balance_response(cls, token_balance_response) -> bool:
        if token_balance_response.get('data').get('ercTokenBalance') is None:
            return False

        return True


class FTMGraphqlResponseParser(ResponseParser):
    validator = FTMGraphqlResponseValidator
    currency = Currencies.ftm
    precision = 18
    symbol = 'FTM'

    @classmethod
    def parse_block_head_response(cls, block_head_response) -> int:
        if cls.validator.validate_block_head_response(block_head_response):
            return int(block_head_response.get('data').get('block').get('number'), 0)

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return []

        transactions: List[TransferTx] = []

        for tx in address_txs_response.get('data').get('account').get('txList').get('edges'):
            if cls.validator.validate_transaction(transaction := tx.get('transaction')):
                confirmations = block_head - int(transaction.get('blockNumber'), 0)
                transactions.append(cls._parse_tx(transaction, confirmations))

        return transactions

    @classmethod
    def parse_batch_block_txs_response(cls, batch_block_txs_response) -> List[TransferTx]:
        if not cls.validator.validate_batch_block_txs_response(batch_block_txs_response):
            return []

        transactions: List[TransferTx] = []

        for block in batch_block_txs_response.get('data').get('blocks').get('edges'):
            for tx in block.get('block').get('txList'):
                if cls.validator.validate_transaction(tx):
                    transactions.append(cls._parse_tx(tx, 0))

        return transactions

    @classmethod
    def parse_balance_response(cls, balance_response) -> Decimal:
        if not cls.validator.validate_general_response(balance_response):
            return Decimal(0)

        if not cls.validator.validate_balance_response(balance_response):
            return Decimal(0)

        return Decimal(
            BlockchainUtilsMixin.from_unit(
                int(balance_response.get('data').get('account').get('balance'), 0),
                precision=cls.precision)
        )

    @classmethod
    def parse_token_balance_response(cls, balance_response, contract_info) -> Decimal:
        if not cls.validator.validate_general_response(balance_response):
            return Decimal(0)

        if not cls.validator.validate_token_balance_response(balance_response):
            return Decimal(0)

        return Decimal(
            BlockchainUtilsMixin.from_unit(
                int(balance_response.get('data').get('ercTokenBalance'), 0),
                precision=contract_info.get('decimals'))
        )

    @classmethod
    def _parse_tx(cls, tx: Dict, confirmations: int) -> TransferTx:

        return TransferTx(
            tx_hash=tx.get('hash'),
            success=tx.get('status') == '0x1',
            from_address=tx.get('from'),
            to_address=tx.get('to'),
            value=BlockchainUtilsMixin.from_unit(int(tx.get('value'), 0), precision=cls.precision),
            symbol=cls.symbol,
            confirmations=confirmations,
            block_height=int(tx.get('blockNumber'), 0),
            block_hash=tx.get('block').get('hash'),
            date=parse_utc_timestamp(int(tx.get('block').get('timestamp'), 0)),
            tx_fee=BlockchainUtilsMixin.from_unit(
                int(tx.get('gas'), 16) * int(tx.get('gasPrice'), 16),
                precision=cls.precision),
            index=int(tx.get('index'), 0),
        )


class FtmGraphqlApi(GeneralApi):
    """
    ***IMPORTANT***
    do not use this API for retrieving transactions because in some cases it returns incorrect inputData
    example: https://ftmscan.com/token/0xf65b6396df6b7e2d8a6270e3ab6c7bb08baef22e
    ***IMPORTANT***
    """
    parser = FTMGraphqlResponseParser
    _base_url = 'https://xapi.fantom.network/'
    symbol = 'FTM'
    USE_PROXY = True
    cache_key = 'ftm'
    SUPPORT_BATCH_GET_BLOCKS = True
    TRANSACTIONS_LIMIT = 50
    supported_requests = {
        'get_balance': '',
        'get_token_balance': '',
        'get_block_head': '',
        'get_address_txs': '',
        'get_block_txs': '',
    }

    @classmethod
    def get_headers(cls):
        return {'Content-Type': 'application/json'}

    @classmethod
    def get_address_txs_body(cls, address):

        return json.dumps({
            'query': """
                query getAddressTransactions ($address: Address!, $limit: Int!) {
                    account (address: $address) {
                        txList (count: $limit) {
                            edges {
                                cursor
                                transaction {
                                    hash
                                    status
                                    from
                                    to
                                    gas
                                    gasPrice
                                    value
                                    index
                                    inputData
                                    blockNumber
                                    block {
                                        hash
                                        timestamp
                                    }
                                }
                            }
                        }
                    }
                }
            """,
            'variables': {
                'address': address,
                'limit': cls.TRANSACTIONS_LIMIT,
            }
        })

    @classmethod
    def get_block_head_body(cls):
        return json.dumps({
            'query': """
                query blockHead {
                    block {
                        number
                    }
                }
            """
        })

    @classmethod
    def get_blocks_txs_body(cls, from_block, to_block):
        if not from_block or not to_block:
            return {}

        if to_block < from_block:
            return {}

        return json.dumps({
            'query': """
                query getBlocksTransactions ($min_height: Cursor!, $count: Int!) {
                    blocks (cursor: $min_height, count: $count) {
                        edges {
                            block {
                                number
                                txList {
                                    hash
                                    status
                                    from
                                    to
                                    gas
                                    gasPrice
                                    value
                                    index
                                    inputData
                                    blockNumber
                                    block {
                                        hash
                                        timestamp
                                    }
                                }
                            }
                        }
                    }
                }
            """,
            'variables': {
                'min_height': hex(to_block + 1),
                'count': to_block - from_block + 1
            }
        })

    @classmethod
    def get_balance_body(cls, address):

        return json.dumps({
            'query': """
                query getAddressBalance ($address: Address!) {
                    account (address: $address) {
                        balance
                    }
                }
            """,
            'variables': {
                'address': address
            }
        })

    @classmethod
    def get_token_balance_body(cls, address, contract_info):

        return json.dumps({
            'query': """
                query($owner: Address!, $token: Address!) {
                    ercTokenBalance(owner: $owner, token: $token)
                }
            """,
            'variables': {
                'owner': address,
                'token': contract_info.get('address')
            }
        })
