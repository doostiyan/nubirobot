import random

from django.conf import settings

from exchange.blockchain.api.apt.aptoslabs_apt import AptoslabsAptApi, AptoslabsAptParser


class AptosChainbase(AptoslabsAptApi):
    """
    API docs: https://docs.chainbase.online/r/chain-apis/aptos-api
    """
    parser = AptoslabsAptParser
    _base_url = 'https://aptos-mainnet.s.chainbase.online'
    rate_limit = 0.3  # 5 QPS, 1M Requests/Month
    instance = None

    supported_requests = {
        'get_block_head': '/{apikey}/v1',
        'get_address_txs': '/{apikey}/v1/accounts/{address}/transactions?sort=desc',
        'get_tx_details': '/{apikey}/v1/transactions/by_version/{tx_hash}',
        'get_blocks_txs': '/{apikey}/v1/transactions?start={start_versionid}&limit={limit}',
    }

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.APTOS_CHAINBASE_API_KEY)
