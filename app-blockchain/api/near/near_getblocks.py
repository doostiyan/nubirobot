import json
import random
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


class NearGetBlockValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.05')
    precision = 24

    @classmethod
    def validate_general_response(cls, response: Dict[str, Any]) -> bool:
        if response.get('error'):
            return False
        if not response or not response.get('result'):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, Any]) -> bool:
        if cls.validate_general_response(block_head_response) and block_head_response.get('result').get('chunks'):
            return True
        return False

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: Dict[str, Any]) -> bool:
        if not block_txs_response or not isinstance(block_txs_response, dict):
            return False
        if block_txs_response.get('error'):
            return False
        if not block_txs_response.get('result') and not block_txs_response.get('result').get('transactions'):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        result = tx_details_response.get('result')
        if not result.get('final_execution_status') or \
                result.get('final_execution_status').casefold() != 'FINAL'.casefold():
            return False
        if not result.get('status') or result.get('status').get('SuccessValue'):
            return False

        return cls.validate_transaction(result.get('transaction'))

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if not transaction.get('actions') or len(transaction.get('actions')) != 1:
            return False
        if not isinstance(transaction.get('actions')[0], dict):
            return False
        if list(transaction.get('actions')[0].keys()) != ['Transfer']:
            return False
        if not transaction.get('actions')[0].get('Transfer').get('deposit'):
            return False
        value = int(transaction.get('actions')[0].get('Transfer').get('deposit'))
        if BlockchainUtilsMixin.from_unit(value, cls.precision) < cls.min_valid_tx_amount:
            return False
        return True

    @classmethod
    def validate_shards_number_response(cls, shards_number_response: Dict[str, Any]) -> bool:
        if not shards_number_response.get('result') or not shards_number_response.get('result', {}).get('chunks'):
            return False
        return True


class NearGetBlockParser(ResponseParser):
    validator = NearGetBlockValidator
    precision = 24
    symbol = 'NEAR'
    currency = Currencies.near
    default_shard_number = 6

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, Any]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return int(block_head_response.get('result').get('chunks')[0].get('height_created'))
        return None

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: Dict[str, Any]) -> List[TransferTx]:
        block_txs: List[TransferTx] = []
        if cls.validator.validate_block_txs_response(block_txs_response):
            header = block_txs_response.get('result').get('header')
            block_hash = header.get('chunk_hash')
            block_height = header.get('height_created')
            for tx in block_txs_response.get('result').get('transactions'):
                if cls.validator.validate_transaction(tx):
                    block_tx = TransferTx(
                        from_address=tx.get('signer_id'),
                        to_address=tx.get('receiver_id'),
                        tx_hash=tx.get('hash'),
                        symbol=cls.symbol,
                        value=BlockchainUtilsMixin.from_unit(int(tx.get('actions')[0].get('Transfer').get('deposit')),
                                                             cls.precision),
                        success=True,
                        block_hash=block_hash,
                        block_height=block_height,
                        confirmations=0,
                        date=None,
                        memo=None,
                        tx_fee=None
                    )
                    block_txs.append(block_tx)
        return block_txs

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, Any], _: int) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response):
            transaction = tx_details_response.get('result').get('transaction')
            tx_hash = transaction.get('hash')
            from_address = transaction.get('signer_id')
            to_address = transaction.get('receiver_id')
            value = BlockchainUtilsMixin.from_unit(int(transaction.get('actions')[0].get('Transfer').get('deposit'))
                                                   , cls.precision)
            return [TransferTx(
                tx_hash=tx_hash,
                success=True,
                from_address=from_address,
                to_address=to_address,
                value=value,
                symbol=cls.symbol
            )]
        return []

    @classmethod
    def parse_shards_number_response(cls, shards_number_response: Dict[str, Any]) -> int:
        if cls.validator.validate_shards_number_response(shards_number_response):
            return len(shards_number_response.get('result').get('chunks'))
        return cls.default_shard_number


class NearGetBlocksApi(GeneralApi):
    """
    Api doc: https://getblock.io/docs/near/json-rpc/
    """
    parser = NearGetBlockParser
    cache_key = 'near'
    symbol = 'NEAR'
    instance = None
    _base_url = 'https://go.getblock.io/'

    @property
    def supported_requests(self) -> Dict[str, str]:
        return {
            'get_block_head': f'{random.choice(settings.NEAR_GETBLOCK_APIKEY)}',
            'get_block_txs': f'{random.choice(settings.NEAR_GETBLOCK_APIKEY)}',
            'get_shards_number': f'{random.choice(settings.NEAR_GETBLOCK_APIKEY)}'
        }

    GET_BLOCK_ADDRESSES_MAX_NUM = 100

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {'content-type': 'application/json'}

    @classmethod
    def get_block_txs(cls, block_height: int, shard_id: int) -> Any:
        try:
            return cls.request(request_method='get_block_txs', body=cls.get_block_txs_body(block_height, shard_id),
                               headers=cls.get_headers(), height=block_height, apikey=cls.get_api_key())
        except APIError as e:
            error_message = str(e)
            # Check if the error contains the specific pattern or message
            if 'UNKNOWN_BLOCK"' in error_message and 'status code: 422' in error_message:
                return None
                # Handle the specific error case here
            # Re-raise the exception if it does not match the specific case
            raise

    @classmethod
    def get_block_head_body(cls) -> str:
        data = {
            'jsonrpc': '2.0',
            'method': 'block',
            'params': {
                'finality': 'final'
            },
            'id': 'getblock.io'
        }
        return json.dumps(data)

    @classmethod
    def get_block_txs_body(cls, block_height: int, shard_id: int) -> str:
        data = {
            'jsonrpc': '2.0',
            'method': 'chunk',
            'params': {
                'block_id': block_height,
                'shard_id': shard_id
            },
            'id': 'getblock.io'
        }
        return json.dumps(data)

    @classmethod
    def get_shards_number_body(cls, block_height: int) -> str:
        data = {
            'jsonrpc': '2.0',
            'method': 'block',
            'params': {
                'block_id': block_height
            },
            'id': 'getblock.io'
        }
        return json.dumps(data)

    @classmethod
    def get_shards_number(cls, block_height: int) -> Any:
        try:
            return cls.request('get_shards_number', body=cls.get_shards_number_body(block_height),
                                   headers=cls.get_headers())
        except APIError as e:
            error_message = str(e)
            # Check if the error contains the specific pattern or message
            if 'UNKNOWN_BLOCK"' in error_message and 'status code: 422' in error_message:
                return None
                # Handle the specific error case here
            # Re-raise the exception if it does not match the specific case
            raise
