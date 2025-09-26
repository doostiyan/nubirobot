import json
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from django.conf import settings

from exchange.blockchain.api.general.dtos import Balance
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator


class BitqueryValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.0005')

    @classmethod
    def validate_general_response(cls, response: Dict[str, any]) -> bool:
        if response.get('errors'):
            return False
        if not response.get('data'):
            return False
        if not response.get('data').get('bitcoin'):
            return False
        return True

    @classmethod
    def validate_balances_response(cls, balance_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(balance_response):
            return False
        general_response = balance_response.get('data').get('bitcoin')
        if not general_response.get('addressStats'):
            return False
        if not isinstance(general_response.get('addressStats'), list):
            return False
        for balance in general_response.get('addressStats'):
            if not balance or not isinstance(balance, dict):
                return False
            if not balance.get('address') or not isinstance(balance.get('address'), dict):
                return False
            if balance.get('address').get('balance') is None:
                return False
            if not balance.get('address').get('address'):
                return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, any]) -> bool:
        cls.validate_general_response(block_head_response)
        if not block_head_response.get('data', {}).get('bitcoin', {}).get('blocks'):
            return False
        if len(block_head_response.get('data').get('bitcoin').get('blocks')) != 1:
            return False
        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(block_txs_response):
            return False
        if not block_txs_response.get('data').get('bitcoin').get('inputs'):
            return False
        if not block_txs_response.get('data').get('bitcoin').get('outputs'):
            return False
        return True

    @classmethod
    def validate_block_tx_transaction(cls, transaction: Dict[str, any]) -> bool:
        if not transaction.get('value'):
            return False
        if transaction.get('value') < cls.min_valid_tx_amount:
            return False
        return True

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response: Dict[str, any]) -> bool:
        if not block_txs_raw_response or not isinstance(block_txs_raw_response, dict):
            return False
        if not block_txs_raw_response.get('data') or not isinstance(block_txs_raw_response, dict):
            return False
        if not block_txs_raw_response.get('data').get('bitcoin') or not isinstance(block_txs_raw_response, dict):
            return False
        if (not block_txs_raw_response.get('data').get('bitcoin').get('inputs')
                and not block_txs_raw_response.get('data').get('bitcoin').get('outputs')):
            return False
        return True


class BitqueryResponseParser(ResponseParser):
    precision = 8
    validator = BitqueryValidator

    @classmethod
    def parse_balances_response(cls, balances_response: Dict[str, any]) -> List[Balance]:
        balances = []
        if cls.validator.validate_balances_response(balances_response):
            for balance in balances_response.get('data').get('bitcoin').get('addressStats'):
                balances.append(
                    Balance(
                        balance=Decimal(str(balance.get('address').get('balance'))),
                        address=balance.get('address').get('address'),
                        symbol=cls.symbol,
                    )
                )
        return balances

    @classmethod
    def convert_address(cls, address: str) -> str:
        return address

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, any]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return int(block_head_response.get('data').get('bitcoin').get('blocks')[0].get('height'))
        return None

    @classmethod
    def parse_batch_block_txs_response(cls, batch_block_txs_response: Dict[str, any]) -> List[TransferTx]:
        input_txs: List[TransferTx] = []
        output_txs: List[TransferTx] = []
        if not cls.validator.validate_block_txs_response(batch_block_txs_response):
            return []
        for block_input in batch_block_txs_response.get('data').get('bitcoin').get('inputs'):
            if not cls.validator.validate_block_tx_transaction(block_input):
                continue
            transfer = cls._parse_block_transfer_tx(block_input, 'input')
            input_txs.append(transfer)

        for block_output in batch_block_txs_response.get('data').get('bitcoin').get('outputs'):
            if not cls.validator.validate_block_tx_transaction(block_output):
                continue
            transfer = cls._parse_block_transfer_tx(block_output, 'output')
            output_txs.append(transfer)

        # Be aware that input value is just correct for one input transactions
        # TODO: check the below code with others
        for input_ in input_txs:
            input_.value = Decimal('0')
            for output in output_txs:
                if output.tx_hash == input_.tx_hash:
                    input_.value += output.value
                    if input_.from_address == output.to_address:
                        input_.value -= output.value
        return input_txs + output_txs

    @classmethod
    def _parse_block_transfer_tx(cls, tx: Dict[str, any], direction: str) -> TransferTx:
        if direction not in ['input', 'output']:
            raise ValueError("Please insert one of input/output as 'direction' argument")

        address = {}
        if direction == 'input':
            from_address = tx.get('inputAddress').get('address')
            legacy_from_address = cls.convert_address(from_address)
            address = {'from_address': legacy_from_address, 'to_address': ''}
        elif direction == 'output':
            to_address = tx.get('outputAddress').get('address')
            legacy_to_address = cls.convert_address(to_address)
            address = {'to_address': legacy_to_address, 'from_address': ''}
        return TransferTx(
            block_height=tx.get('block').get('height'),
            value=Decimal(str(tx.get('value'))),
            success=True,
            symbol=cls.symbol,
            tx_hash=tx.get('transaction').get('hash'),
            **address
        )


class BitqueryApi(GeneralApi):
    """
        API docs: https://graphql.bitquery.io/ide
        Explorer: https://explorer.bitquery.io/ltc
    """
    USE_PROXY = False
    parser = BitqueryResponseParser
    BITQUERY_NETWORK = None
    SUPPORT_BATCH_GET_BLOCKS = True
    SUPPORT_GET_BALANCE_BATCH = True
    PAGINATION_OFFSET = 0
    _base_url = 'https://graphql.bitquery.io'

    supported_requests = {
        'get_block_head': '',
        'get_block_txs': '',
        'get_balance': ''
    }

    queries = {
        'get_block_head': """
            query getBlockHead($network: BitcoinNetwork!, $limit: Int!, $offset: Int!, $from: ISO8601DateTime) {
                bitcoin(network: $network) {
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
                query getBalance($network: BitcoinNetwork!, $addresses: [String!]) {
                    bitcoin(network: $network) {
                        addressStats(address: {in: $addresses}) {
                          address {
                            balance
                            address
                          }
                        }
                    }
                } """,
        'get_block_txs': """
          query getBlockTxs($network: BitcoinNetwork!, $fromBlock: Int!, $toBlock: Int!, $fromDateTime: ISO8601DateTime!, $toDateTime: ISO8601DateTime!) {  # noqa F401
              bitcoin(network: $network) {
                inputs(
                  height: {gteq: $fromBlock, lteq: $toBlock}
                  options: {desc: "block.height"}
                  date: {since: $fromDateTime, till: $toDateTime}
                ) {
                  block {
                    height
                  }
                  inputAddress {
                    address
                  }
                  value
                  transaction {
                    hash
                  }
                }
                outputs(
                  height: {gteq: $fromBlock, lteq: $toBlock}
                  options: {desc: "block.height"}
                  date: {since: $fromDateTime, till: $toDateTime}
                ) {
                  value
                  outputAddress {
                    address
                  }
                  transaction {
                    hash
                  }
                  block {
                    height
                  }
                }
              }
            }
        """,  # noqa: E501
    }

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.get_api_key()
        }

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.BTC_BITQUERY_API_KEY)

    @classmethod
    def get_block_head_body(cls) -> str:
        from_time = datetime.now().isoformat()
        data = {
            'query': cls.queries.get('get_block_head'),
            'variables': {
                'network': cls.BITQUERY_NETWORK,
                'limit': 1,
                'offset': cls.PAGINATION_OFFSET,
                'from': from_time,
            }
        }
        return json.dumps(data)

    @classmethod
    def get_blocks_txs_body(cls, from_block: int, to_block: int) -> str:
        to_datetime = datetime.now()
        from_datetime = to_datetime - timedelta(days=6)
        data = {
            'query': cls.queries.get('get_block_txs'),
            'variables': {
                'network': cls.BITQUERY_NETWORK,
                'fromBlock': from_block,
                'toBlock': to_block,
                'fromDateTime': from_datetime.isoformat(),
                'toDateTime': to_datetime.isoformat(),
            }
        }
        return json.dumps(data)

    @classmethod
    def get_balances_body(cls, addresses: List[str]) -> str:
        data = {
            'query': cls.queries.get('get_balance'),
            'variables': {
                'network': cls.BITQUERY_NETWORK,
                'addresses': addresses,
            }
        }
        return json.dumps(data)
