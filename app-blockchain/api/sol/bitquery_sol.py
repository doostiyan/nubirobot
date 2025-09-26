import datetime
import json
import random
from decimal import Decimal
from typing import List, Optional

from django.conf import settings

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import APIError

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class BitQuerySolValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.001')
    valid_program_id = '11111111111111111111111111111111'

    @classmethod
    def validate_general_response(cls, response: dict) -> bool:
        if not response:
            return False
        if not isinstance(response, dict) or 'errors' in response:
            raise APIError('[BitQuerySolAPI][ValidateGeneralResponse]' + response.get('errors')[0].get('message'))
        if not response.get('data'):
            return False
        if not response.get('data').get('solana'):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: dict) -> bool:
        if (cls.validate_general_response(block_head_response)
                and block_head_response.get('data').get('solana').get('blocks')):
            return True
        return False

    @classmethod
    def validate_transaction(cls, transaction: dict) -> bool:
        # A 'program' in Solana represents a smart contract that facilitates various
        # blockchain operations and interactions within the network.
        if (not transaction.get('instruction')
                or not transaction.get('instruction').get('program')
                or not transaction.get('instruction').get('externalProgram')):
            return False
        program = transaction.get('instruction').get('program')
        external_program = transaction.get('instruction').get('externalProgram')
        if (transaction.get('currency').get('symbol') != 'SOL'
                or not transaction.get('transaction').get('signature')  # not empty hash
                or Decimal(str(transaction.get('amount'))) <= cls.min_valid_tx_amount
                or not transaction.get('transaction').get('success') or transaction.get('transaction').get('error')
                or transaction.get('receiver').get('address').casefold() ==
                transaction.get('sender').get('address').casefold()
                # Check the name and address of the transaction's program
                # If the program name is not "system" or the address
                # is not the valid address "11111111111111111111111111111111",
                # consider the transaction invalid.
                or program.get('id') != cls.valid_program_id
                or not program.get('parsed')
                or program.get('name').casefold() != 'system'.casefold()
                or external_program.get('id') != cls.valid_program_id
                or not external_program.get('parsed')
                or external_program.get('name').casefold() != 'system'.casefold()
                or transaction.get('instruction').get('action').get('name').casefold() != 'transfer'.casefold()
                or transaction.get('instruction').get('externalAction').get('name').casefold()
                != 'transfer'.casefold()):  # valid type
            return False
        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: dict) -> bool:
        if (cls.validate_general_response(block_txs_response)
                and block_txs_response.get('data').get('solana').get('transfers')):
            return True
        return False


class BitQuerySolParser(ResponseParser):
    validator = BitQuerySolValidator
    symbol = 'SOL'
    currency = Currencies.sol

    @classmethod
    def parse_block_head_response(cls, block_head_response: dict) -> Optional[int]:
        return int(block_head_response.get('data').get('solana').get('blocks')[0].get('height')) \
            if cls.validator.validate_block_head_response(block_head_response) else None

    @classmethod
    def parse_batch_block_txs_response(cls, block_txs_response: dict) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=transfer.get('block').get('height'),
                block_hash=None,
                tx_hash=transfer.get('transaction').get('signature'),
                date=None,
                success=True,
                confirmations=None,
                from_address=transfer.get('sender').get('address'),
                to_address=transfer.get('receiver').get('address'),
                value=Decimal(str(transfer.get('amount'))),
                symbol=cls.symbol,
                memo=None,
                tx_fee=None,
                token=None,
            )
            for transfer in block_txs_response.get('data').get('solana').get('transfers')
            if cls.validator.validate_transaction(transfer)
        ] if cls.validator.validate_block_txs_response(block_txs_response) else []


class BitQuerySolApi(GeneralApi):
    """
        coins: SOL
        API docs: https://graphql.bitquery.io/ide
        exception ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut
    """
    parser = BitQuerySolParser
    symbol = 'SOL'
    cache_key = 'sol'
    SUPPORT_BATCH_GET_BLOCKS = True
    _base_url = 'https://graphql.bitquery.io/'
    rate_limit = 6
    GET_BLOCK_ADDRESSES_MAX_NUM = 300
    END_BLOCK_RANGE_WITH_PROBLEM = 0
    # Setting the 'block_height_offset' to 1500 ensures a safe margin from the
    # latest block height in the network, preventing potential errors and ensuring smooth and reliable operations
    block_height_offset = 1500
    timeout = 60
    supported_requests = {
        'get_block_head': '',
        'get_block_txs': ''
    }
    queries = {
        'get_block_head': """
                query ($network: SolanaNetwork!, $limit: Int!, $offset: Int!, $from: ISO8601DateTime) {
                    solana(network: $network) {
                        blocks(
                            options: {desc: "height", limit: $limit, offset: $offset}
                            date: {since: $from}
                        ) {
                        height
                    }
                  }
                }
            """,
        'get_blocks': """
            query ($from: Int!, $to: Int!, $fromDate: ISO8601DateTime!, $toDate: ISO8601DateTime!) {
                solana(network: solana) {
                    transfers(
                        success: {is: true}
                        transferType: {is: transfer}
                        currency: {is: "SOL"}
                        height: {between: [$from, $to]}
                        programId: {is: "11111111111111111111111111111111"}
                        externalProgramId: {is: "11111111111111111111111111111111"}
                        date: {between: [$fromDate, $toDate]}
                    )  {
                        transaction {
                            signature
                            success
                            error
                        }
                        sender {
                            address
                        }
                        receiver {
                            address
                        }
                        currency {
                            symbol
                        }
                        block {
                            height
                        }
                        amount
                        instruction {
                            externalProgram {
                            id
                            parsed
                            name
                            }
                            action {
                                name
                            }
                            program {
                                id
                                parsed
                                name
                            }
                            externalAction {
                                name
                            }
                        }
                    }
                }
            }
        """,
    }

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.BITQUERY_API_KEY)

    @classmethod
    def get_headers(cls) -> dict:
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.get_api_key(),
            'accept-encoding': 'gzip'
        }

    @classmethod
    def get_block_head_body(cls) -> str:
        data = {
            'query': cls.queries.get('get_block_head'),
            'variables': {
                'from': (datetime.datetime.utcnow()).isoformat(),
                'limit': 1,
                'offset': 0,
                'network': 'solana'
            }
        }
        return json.dumps(data)

    @classmethod
    def get_blocks_txs_body(cls, from_block: int, to_block: int) -> str:
        now_date = datetime.datetime.now()
        data = {
            'query': cls.queries.get('get_blocks'),
            'variables': {
                'from': from_block,
                'to': to_block,
                'fromDate': (now_date - datetime.timedelta(days=4)).isoformat(),
                'toDate': now_date.isoformat()
            }
        }
        return json.dumps(data)
