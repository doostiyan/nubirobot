import random
from django.conf import settings
from exchange.blockchain.api.apt.aptoslabs_apt import AptoslabsAptApi, AptoslabsAptParser


class AptosNodeReal(AptoslabsAptApi):
    parser = AptoslabsAptParser
    _base_url = 'https://aptos-mainnet.nodereal.io/v1'
    instance = None
    supported_requests = {
        'get_block_head': '/{apikey}/v1',
        'get_address_txs': '/{apikey}/v1/accounts/{address}/transactions?sort=desc',
        'get_tx_details': '/{apikey}/v1/transactions/by_version/{tx_hash}',
    }

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.APTOS_NODEREAL_API_KEY)
