import json
import random
import time
from typing import Any, Optional, Tuple

from django.conf import settings
from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI
from exchange.blockchain.metrics import metric_set
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


class SolFlipsidecrypto(NobitexBlockchainBlockAPI, BlockchainUtilsMixin):
    """
    coins: Solana
    API docs: https://docs.flipsidecrypto.com/shroomdk-sdk
    """
    rate_limit = 1.2  # 250 in 5 min
    PRECISION = 9
    symbol = 'SOL'
    currency = Currencies.sol
    SUPPORT_BATCH_BLOCK_PROCESSING = True
    GET_BLOCK_ADDRESSES_MAX_NUM = 5000
    cache_key = 'sol'
    supported_requests = {
        'get_query': '',
        'get_query_result': '/{query_token}',
    }

    _base_url = 'https://api-v2.flipsidecrypto.xyz/json-rpc'

    @staticmethod
    def get_api_key() -> str:
        return random.choice(settings.FLOW_SHROOM_API_KEYS)

    @property
    def headers(self) -> dict:
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'x-api-key': self.get_api_key(),
            'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0'
        }

    def execute_query(self, query: str) -> Any:
        query_token = self.request('get_query', body=query)
        time.sleep(5)
        payload = json.dumps({
            'jsonrpc': '2.0',
            'method': 'getQueryRunResults',
            'params': [
                {
                    'queryRunId': query_token.get('result').get('queryRequest').get('queryRunId'),
                    'format': 'csv',
                    'page': {
                        'number': 1,
                        'size': 100000
                    }
                }
            ],
            'id': 1
        })
        query_result = self.request('', body=payload)
        i = 0
        message = query_result.get('error', {}).get('message', '')
        while 'QueryRunNotFinished' in message:
            time.sleep(5)
            query_result = self.request('', body=payload)
            i += 1
            message = query_result.get('error', {}).get('message', '')
            if i == 5 and 'QueryRunNotFinished' in message:  # noqa: PLR2004
                raise APIError(f'{self.symbol} API: Get Txs. Getting query result is not finished yet.')
        return query_result

    def get_block_head(self) -> Any:
        query = """
                    select block_id from solana.core.fact_blocks ORDER by block_id DESC LIMIT 1
                """
        payload = json.dumps({
            'jsonrpc': '2.0',
            'method': 'createQueryRun',
            'params': [
                {
                    'resultTTLHours': 1,
                    'maxAgeMinutes': 0,
                    'sql': query,
                    'tags': {
                        'source': 'postman-demo',
                        'env': 'test'
                    },
                    'dataSource': 'snowflake-default',
                    'dataProvider': 'flipside'
                }
            ],
            'id': 1
        })

        query_result = self.execute_query(payload)
        if query_result.get('result') is None or len(query_result.get('result').get('rows', [])) != 1:
            raise APIError(f'{self.symbol} API: Get Txs response is None')

        return query_result.get('result').get('rows')[0][0]

    def get_blocks(self, min_height: int, max_height: int, _: str = '') -> list:
        query = f"""
            SELECT
              *
            FROM
              solana.core.FACT_events
            WHERE
              EVENT_TYPE = 'transfer'
              AND PROGRAM_ID = '11111111111111111111111111111111'
              AND SUCCEEDED = TRUE
              AND BLOCK_ID BETWEEN {min_height} AND {max_height - 1}
            ORDER by
              block_id
        """  # noqa: S608
        payload = json.dumps({
            'jsonrpc': '2.0',
            'method': 'createQueryRun',
            'params': [
                {
                    'resultTTLHours': 1,
                    'maxAgeMinutes': 0,
                    'sql': query,
                    'tags': {
                        'source': 'postman-demo',
                        'env': 'test'
                    },
                    'dataSource': 'snowflake-default',
                    'dataProvider': 'flipside'
                }
            ],
            'id': 1
        })
        query_result = self.execute_query(payload)
        if query_result.get('result') is None or len(query_result.get('result').get('rows', [])) == 0:
            raise APIError(f'{self.symbol} API: Get Txs response is None')
        return [query_result]

    def parse_block(self, blocks: dict) -> Any:
        return blocks.get('result').get('rows')

    def parse_transaction_data(self, tx: list) -> dict:
        parsed_instruction = tx[8].get('parsed')

        if not parsed_instruction.get('info').get('source'):
            pass
        if not parsed_instruction.get('info').get('destination'):
            pass
        return {
            'hash': tx[2],
            'from': parsed_instruction.get('info').get('source'),
            'to': parsed_instruction.get('info').get('destination'),
            'amount': self.from_unit(parsed_instruction.get('info').get('lamports')),
            'currency': self.currency,
        }

    def validate_transaction(self, tx: list, _: Optional[str] = None) -> bool:
        if not tx[4]:
            return False
        if tx[6] != 'transfer':
            return False
        instruction = tx[8]
        if instruction.get('program') != 'system' or instruction.get('programId') != '11111111111111111111111111111111':
            return False
        parsed_instruction = instruction.get('parsed')
        if not parsed_instruction or parsed_instruction.get('type') != 'transfer':
            return False
        return True

    def get_latest_block(self, after_block_number: Optional[int] = None, to_block_number: Optional[int] = None,
                         include_inputs: bool = False, include_info: bool = False, update_cache: bool = True) -> Tuple[
        dict, dict, int]:
        """
        calculate unprocessed block-height range and list all addresses in all transaction in all blocks in that range
        """
        max_height, min_height = self.calculate_unprocessed_block_range(after_block_number, to_block_number)

        blocks = self.get_blocks(min_height=min_height, max_height=max_height, tx_filter_query=self.TX_FILTER_QUERY)

        transactions_addresses, transactions_info = self.get_block_addresses(blocks, include_inputs=include_inputs,
                                                                             include_info=include_info)
        block_height = 0
        if blocks and update_cache and blocks[0].get('result'):
            block_height = blocks[0].get('result').get('rows')[-1][1]
            metric_set(name='latest_block_processed', labels=[self.symbol.lower()], amount=block_height)
            cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}',
                      block_height, 86400)
        return transactions_addresses, transactions_info, block_height
