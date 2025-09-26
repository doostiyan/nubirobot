import json

from exchange.blockchain.api.near.near_getblocks import NearGetBlocksApi


class NearRpcAPI(NearGetBlocksApi):
    rate_limit = 0.1  # 600 req per min
    USE_PROXY = True

    # https://free.rpc.fastnear.com
    # https://rpc.web4.near.page
    # https://near-mainnet-rpc.allthatnode.com/e00988fsrFxmpWjTI47q4BHJO3zJ2esK
    # https://rpc.mainnet.near.org
    # https://near-mainnet.api.pagoda.co/rpc/v1
    # https://near.lavenderfive.com/
    # https://near.blockpi.network/v1/rpc/public
    # https://near.drpc.org
    _base_url = 'https://near.lava.build' #'https://red-weathered-surf.near-mainnet.quiknode.pro/f71db496c0d6173452a4f21b09c866b89e5a4bc6'

    supported_requests = {
        'get_block_head': '',
        'get_block_txs': '',
        'get_shards_number': ''
    }
    instance = None

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
