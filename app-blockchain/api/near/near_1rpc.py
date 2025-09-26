import json
import random
from typing import Any, Dict

from django.conf import settings

from exchange.blockchain.api.near.near_getblocks import NearGetBlocksApi


class Near1RpcAPI(NearGetBlocksApi):
    _base_url = 'https://free.rpc.fastnear.com'
    supported_requests = {
        'get_tx_details': ''
    }
    need_block_head_for_confirmation = False
    instance = None

    @classmethod
    def get_tx_details_body(cls, tx_hash: str) -> str:
        data = {
            'jsonrpc': '2.0',
            'id': 'dontcare',
            'method': 'tx',
            'params': {
                'tx_hash': tx_hash,
                'sender_account_id': 'sender.mainnet',
                'wait_until': 'EXECUTED'
            }
        }
        return json.dumps(data)


class NearTatumApi(Near1RpcAPI):
    _base_url = 'https://near-mainnet.gateway.tatum.io'

    @classmethod
    def get_headers(cls) -> Dict[str, Any]:
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.get_api_key()
        }

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.TATUM_API_KEYS)
