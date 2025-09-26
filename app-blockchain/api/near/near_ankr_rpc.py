import json

from exchange.blockchain.api.near.near_getblocks import NearGetBlocksApi


class NearAnkrRpcAPI(NearGetBlocksApi):
    rate_limit = 0.033  # 30 rps
    _base_url = 'https://rpc.ankr.com/near'
    instance = None
    supported_requests = {
        'get_block_head': '',
        'get_block_txs': '',
        'get_shards_number': ''
    }

    @classmethod
    def get_block_head_body(cls) -> str:
        data = {
            'jsonrpc': '2.0',
            'method': 'block',
            'params': {
                'finality': 'final'
            },
            'id': 'dontcare'
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
            'id': 'dontcare'
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
            'id': 'dontcare'
        }
        return json.dumps(data)
