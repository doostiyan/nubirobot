import json
from typing import Any, Dict, List

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.near.near_getblocks import NearGetBlockParser, NearGetBlockValidator
from exchange.blockchain.api.near.near_rpc import NearRpcAPI
from exchange.blockchain.utils import BlockchainUtilsMixin


class NearQuickNodeResponseValidator(NearGetBlockValidator):

    @classmethod
    def validate_batch_block_txs_response(cls, batch_block_txs_response: Any) -> bool:
        if not batch_block_txs_response or not isinstance(batch_block_txs_response, list):
            return False
        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: Dict[str, Any]) -> bool:
        if not block_txs_response or not isinstance(block_txs_response, dict):
            return False
        if block_txs_response.get('error'):
            return False
        if not block_txs_response.get('result') or not isinstance(block_txs_response.get('result'), dict):
            return False
        if (not block_txs_response.get('result').get('transactions') or
                not isinstance(block_txs_response.get('result').get('transactions'), list)):
            return False
        return True


class NearQuickNodeResponseParser(NearGetBlockParser):
    validator = NearQuickNodeResponseValidator

    @classmethod
    def parse_batch_block_txs_response(cls, batch_block_txs_response:List[Dict[str,Any]]) -> List[TransferTx]:
        blocks_txs: List[TransferTx] = []
        if cls.validator.validate_batch_block_txs_response(batch_block_txs_response):
            for block_txs_response in batch_block_txs_response:
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
                                value=BlockchainUtilsMixin.from_unit(
                                    int(tx.get('actions')[0].get('Transfer').get('deposit')),
                                    cls.precision),
                                success=True,
                                block_hash=block_hash,
                                block_height=block_height,
                                confirmations=None,
                                date=None,
                                memo=None,
                                tx_fee=None
                            )
                            blocks_txs.append(block_tx)
        return blocks_txs


class NearQuickNodeApi(NearRpcAPI):
    _base_url = 'https://red-weathered-surf.near-mainnet.quiknode.pro/f71db496c0d6173452a4f21b09c866b89e5a4bc6'
    instance = None
    SUPPORT_BATCH_GET_BLOCKS = True
    parser = NearQuickNodeResponseParser
    GET_BLOCK_ADDRESSES_MAX_NUM = 300
    block_step = 5
    shard_step = 6
    number_of_workers = 1

    @classmethod
    def get_batch_block_txs(cls, from_block: int, to_block: int, start_shard: int = 0, end_shard: int = 5) -> Any:

        # Customize the request body to include shard range
        body = cls.get_blocks_txs_body(from_block, to_block, start_shard, end_shard)

        # Send the request
        return cls.request(
            request_method='get_blocks_txs',
            body=body,
            headers=cls.get_headers(),
            from_block=from_block,
            to_block=to_block,
            timeout=cls.timeout
        )

    @classmethod
    def get_blocks_txs_body(cls, from_block: int, to_block: int, start_shard: int = 0, end_shard: int = 5) -> Any:
        final_data = []

        for block_number in range(from_block, to_block + 1):
            for shard_id in range(start_shard, end_shard + 1):
                data = {
                    'jsonrpc': '2.0',
                    'id': 'dontcare',
                    'method': 'chunk',
                    'params': {
                        'block_id': block_number,
                        'shard_id': shard_id
                    }
                }
                final_data.append(data)
        return json.dumps(final_data)


class NearDrpcApi(NearQuickNodeApi):
    instance = None
    block_step = 1
    shard_step = 3
    GET_BLOCK_ADDRESSES_MAX_NUM = 200
    _base_url = 'https://near.drpc.org'
    number_of_workers = 3
