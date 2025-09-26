import datetime
import json
import random
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.conf import settings

from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI


class FlowBitqueryFlowValidator(ResponseValidator):
    FEE_ADDRESS = '0xf919ee77447b7497'
    FLOW_TOKEN_CONTRACT = '1654653399040a61'  # noqa: S105
    DEPOSIT_EVENT_CONTRACT = f'A.{FLOW_TOKEN_CONTRACT}.FlowToken.TokensDeposited'
    WITHDRAW_EVENT_CONTRACT = f'A.{FLOW_TOKEN_CONTRACT}.FlowToken.TokensWithdrawn'

    @classmethod
    def validate_general_response(cls, response: Dict[str, Any]) -> bool:
        if not response:
            return False
        if not response.get('data'):
            return False
        if not response.get('data').get('flow'):
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(balance_response):
            return False
        needed_balance_response = balance_response.get('data').get('flow')
        if not needed_balance_response.get('address'):
            return False
        if not needed_balance_response.get('address')[0].get('balance'):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        needed_block_head_response = block_head_response.get('data').get('flow')
        if not needed_block_head_response.get('blocks'):
            return False
        if not needed_block_head_response.get('blocks')[0].get('height'):
            return False
        if not isinstance(needed_block_head_response.get('blocks')[0].get('height'), str):
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if not transaction.get('transaction').get('id'):
            return False
        if transaction.get('transaction').get('statusCode') != 0:
            return False
        if transaction.get('transferReason') != 'fungible_token_transfer':
            return False
        if transaction.get('currency').get('name').casefold() != 'FlowToken'.casefold() and transaction.get(
                'currency').get('address') != 'A.1654653399040a61.FlowToken':
            return False
        if not transaction.get('type') or (
                transaction.get('type').casefold() != 'TokensDeposited'.casefold() and transaction.get(
            'type').casefold() != 'TokensWithdrawn'.casefold()):
            return False
        if transaction.get('amountDecimal').count('.') != 1:
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        needed_address_txs_response = address_txs_response.get('data').get('flow')
        if not needed_address_txs_response.get('blocks') or not needed_address_txs_response.get('blocks')[0]:
            return False
        if not needed_address_txs_response.get('blocks')[0].get('height'):
            return False
        if not isinstance(needed_address_txs_response.get('blocks')[0].get('height'), str):
            return False
        if not needed_address_txs_response.get('inputs'):
            return False
        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(block_txs_response):
            return False
        needed_block_txs_response = block_txs_response.get('data').get('flow')
        if needed_block_txs_response.get('inputs') is None or needed_block_txs_response.get('outputs') is None:
            return False
        return True


class FlowBitqueryResponseParser(ResponseParser):
    """
        coins: Flow
        API docs: https://developers.flow.com/http-api
        rate limit: https://developers.flow.com/nodes/access-api-rate-limits
        get latest block rate limit : 100 request per second per client IP
        other request rate limit: 2000 rps

        """
    symbol = 'FLOW'
    precision = 8
    min_valid_tx_amount = Decimal('0.0')
    currency = Currencies.flow
    validator = FlowBitqueryFlowValidator
    FEE_ADDRESS = '0xf919ee77447b7497'
    excluded_addresses = ['0x1bf2b9d59ad1ba04']

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, Any]) -> Decimal:
        if cls.validator.validate_balance_response(balance_response):
            return Decimal(str(balance_response.get('data').get('flow').get('address')[0].get('balance')))
        return Decimal(0)

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, Any]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return int(block_head_response.get('data').get('flow').get('blocks')[0].get('height'))
        return None

    @classmethod
    def parse_address_txs_response(cls,
                                   _: str,
                                   address_txs_response: Dict[str, Any],
                                   __: Optional[int]) -> List[TransferTx]:
        address_txs: List[TransferTx] = []
        if cls.validator.validate_address_txs_response(address_txs_response):
            transactions = address_txs_response.get('data').get('flow').get('inputs') + address_txs_response.get(
                'data').get('flow').get('outputs')
            for transaction in transactions:
                from_address = ''
                to_address = ''
                if cls.validator.validate_transaction(transaction):
                    if transaction.get('type').casefold() == 'TokensWithdrawn'.casefold():
                        from_address = transaction.get('address').get('address')
                    else:
                        to_address = transaction.get('address').get('address')
                    date = parse_iso_date(f"{transaction.get('time').get('time').replace(' ', 'T')}Z")
                    block_head = int(address_txs_response.get('data').get('flow').get('blocks')[0].get('height'))
                    block_height = int(transaction.get('block').get('height'))
                    confirmations = block_head - block_height + 1
                    tx_hash = transaction.get('transaction').get('id')
                    transfer = TransferTx(
                        block_height=block_height,
                        value=Decimal(transaction.get('amountDecimal')),
                        date=date,
                        success=True,
                        symbol=cls.symbol,
                        confirmations=confirmations,
                        from_address=from_address,
                        to_address=to_address,
                        tx_hash=tx_hash,
                    )
                    address_txs.append(transfer)
        return address_txs

    @classmethod
    def parse_batch_block_txs_response(cls, batch_block_txs_response: Dict[str, Any]) -> List[TransferTx]:
        if cls.validator.validate_block_txs_response(batch_block_txs_response):
            transactions = batch_block_txs_response.get('data').get('flow').get(
                'inputs') + batch_block_txs_response.get('data').get('flow').get('outputs')
            blocks_txs: List[TransferTx] = []
            for transaction in transactions:
                if cls.validator.validate_transaction(transaction):
                    if transaction.get('type').casefold() == 'TokensWithdrawn'.casefold():
                        from_address = transaction.get('address').get('address')
                        to_address = ''
                    else:
                        from_address = ''
                        to_address = transaction.get('address').get('address')
                    date = parse_iso_date(f"{transaction.get('time').get('time').replace(' ', 'T')}Z")
                    block_height = int(transaction.get('block').get('height'))
                    tx_hash = transaction.get('transaction').get('id')
                    transfer = TransferTx(
                        block_height=block_height,
                        value=Decimal(transaction.get('amountDecimal')),
                        date=date,
                        success=True,
                        symbol=cls.symbol,
                        from_address=from_address,
                        to_address=to_address,
                        tx_hash=tx_hash,
                    )
                    blocks_txs.append(transfer)
            return blocks_txs
        return []


class FlowBitqueryApi(GeneralApi, NobitexBlockchainBlockAPI):
    """
            coins: Flow
            API docs: https://graphql.bitquery.io/ide
            Explorer: https://explorer.bitquery.io/flow
    """
    symbol = 'FLOW'
    cache_key = 'flow'
    currency = Currencies.flow
    PAGINATION_LIMIT = 25
    PAGINATION_OFFSET = 0
    SUPPORT_BATCH_GET_BLOCKS = True
    GET_BLOCK_ADDRESSES_MAX_NUM = 1500
    need_block_head_for_confirmation = False
    FEE_ADDRESS = '0xf919ee77447b7497'
    valid_transfer_types = [
        FlowBitqueryResponseParser.validator.DEPOSIT_EVENT_CONTRACT,
        FlowBitqueryResponseParser.validator.WITHDRAW_EVENT_CONTRACT
    ]
    parser = FlowBitqueryResponseParser
    _base_url = 'https://graphql.bitquery.io'
    excluded_addresses = ['0x1bf2b9d59ad1ba04']

    supported_requests = {
        'get_block_head': '',
        'get_address_txs': '',
        'get_block_txs': '',
        'get_balance': ''
    }

    queries = {
        'get_block_head': """
                query ($limit: Int!, $offset: Int!, $from: ISO8601DateTime) {
                    flow(network: flow) {
                        blocks(
                            options: {desc: "height", limit: $limit, offset: $offset}
                            date: {since: $from}
                        )
                        {
                          height
                        }
                    }
                } """,
        'get_balance': """
                    query ($input: String) {
                        flow(network: flow) {
                            address( address : {is : $input}){
                            balance
                            }
                        }
                    } """,
        'get_address_txs': """
                query getTxs($input: String, $output: String, $limit: Int!, $offset: Int!, $from: ISO8601DateTime) {
                    flow {
                         blocks(
                            options: {desc: "height", limit: 1, offset: $offset}
                            date: {since: $from}
                        )
                        {
                          height
                        }
                        inputs(
                            address: {is: $input}
                            options: {limit: $limit, offset: $offset, desc: "time.time"}
                            currency: {in: "FlowToken"}
                            transactionStatusCode: {is: 0}
                            date: {since: $from}
                            transferReason: {is: fungible_token_transfer}
                            type: {is: "TokensDeposited"}
                        ) {
                            block {
                                height
                            }
                            type
                            amountDecimal
                            currency {
                                name
                                address
                            }
                            transferReason
                            transaction {
                                id
                                statusCode
                            }
                            time {
                                time(format: "%Y-%m-%d %H:%M:%S")
                            }
                            address {
                                address
                            }
                        }
                        outputs(
                            options: {desc: "time.time", limit: $limit, offset: $offset}
                            address: {is: $output}
                            transferReason: {is: fungible_token_transfer}
                            currency: {in: "FlowToken"}
                            transactionStatusCode: {is: 0}
                            date: {since: $from}
                            type: {is: "TokensWithdrawn"}
                        ) {
                            time {
                                time(format: "%Y-%m-%d %H:%M:%S")
                            }
                            transaction {
                                id
                                statusCode
                            }
                            amountDecimal
                            transferReason
                            currency {
                                name
                                address
                            }
                            type
                            block {
                                height
                            }
                            address {
                                address
                            }
                        }
                    }
                }
            """,

        'get_block_txs': """
                query getBlockTxs($from: Int!, $to: Int!) {
                    flow {
                        inputs(
                            height: {between: [$from, $to]}
                            currency: {in: "FlowToken"}
                            transactionStatusCode: {is: 0}
                            transferReason: {is: fungible_token_transfer}
                            address: {not: "0xf919ee77447b7497"}
                        ) {
                            block {
                                height
                            }
                            type
                            currency {
                                name
                                address
                            }
                            transferReason
                            transaction {
                                id
                                statusCode
                            }
                            amountDecimal
                            address {
                                address
                            }
                            time {
                                time(format: "%Y-%m-%d %H:%M:%S")
                            }
                        }
                        outputs(
                            height: {between: [$from, $to]}
                            transferReason: {is: fungible_token_transfer}
                            currency: {in: "FlowToken"}
                            transactionStatusCode: {is: 0}
                        ) {
                            time {
                                time(format: "%Y-%m-%d %H:%M:%S")
                            }
                            transaction {
                                id
                                statusCode
                            }
                            transferReason
                            currency {
                                name
                                address
                            }
                            type
                            amountDecimal
                            address {
                                address
                            }
                            block {
                                height
                            }
                        }
                    }
                }
            """,
        'check_api_correctness': """
                query MyQuery {
                    flow {
                    inputs(
                      transactionId: {in: "c7851221b77faa84c78fabbb237c3de7f38b49d1f08880b2bcaca9976649e331"}
                      type: {in: "TokensDeposited"}
                    ) {
                      amount
                      address {
                        address
                      }
                      currency {
                        tokenId
                      }
                      type
                    }
                    outputs(
                      transactionId: {in: "c7851221b77faa84c78fabbb237c3de7f38b49d1f08880b2bcaca9976649e331"}
                      type: {in: "TokensWithdrawn"}
                    ) {
                      amount
                      address {
                        address
                      }
                      currency {
                        tokenId
                      }
                      type
                    }
                  }
                }
            """
    }

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {cls.get_api_key()}'
        }

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.FLOW_BITQUERY_API_KEY)

    @classmethod
    def get_block_head_body(cls) -> str:
        from_time = datetime.datetime.now().isoformat()
        data = {
            'query': cls.queries.get('get_block_head'),
            'variables': {
                'limit': 1,
                'offset': cls.PAGINATION_OFFSET,
                'from': from_time,
            }
        }
        return json.dumps(data)

    @classmethod
    def get_address_txs_body(cls, address: str) -> str:
        since = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        data = {
            'query': cls.queries.get('get_address_txs'),
            'variables': {
                'limit': cls.PAGINATION_LIMIT,
                'offset': cls.PAGINATION_OFFSET,
                'input': address,
                'output': '',
                'from': since
            }
        }
        return json.dumps(data)

    @classmethod
    def get_balance_body(cls, address: str) -> str:
        data = {
            'query': cls.queries.get('get_balance'),
            'variables': {
                'input': address
            }
        }
        return json.dumps(data)

    @classmethod
    def get_blocks_txs_body(cls, from_block: int, to_block: int) -> str:
        data = {
            'query': cls.queries.get('get_block_txs'),
            'variables': {
                'from': from_block,
                'to': to_block
            }
        }
        return json.dumps(data)
