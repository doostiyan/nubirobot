import random

from django.conf import settings
from exchange.blockchain.api.algorand.algorand_algoexplorer import AlgoExplorerAlgorandApi, \
    AlgoExplorerAlgorandResponseParser, AlgoExplorerAlgorandValidator

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class AlgoNodeAlgorandValidator(AlgoExplorerAlgorandValidator):
    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        if transaction.get('genesis-hash') != 'wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=':
            return False
        return super().validate_transaction(transaction)


class AlgoNodeAlgorandResponseParser(AlgoExplorerAlgorandResponseParser):
    validator = AlgoNodeAlgorandValidator
    symbol = 'ALGO'
    currency = Currencies.algo
    precision = 6


class AlgoNodeAlgorandApi(AlgoExplorerAlgorandApi):
    _base_url = 'https://mainnet-idx.algonode.cloud/'
    rate_limit = 0.017  # 60 rps
    instance = None
    SUPPORT_BATCH_GET_BLOCKS = True
    parser = AlgoNodeAlgorandResponseParser
    max_blocks_limit = 100


class NodeRealAlgorandApi(AlgoNodeAlgorandApi):
    # We have apikey in the base_url
    _base_url = f'https://open-platform.nodereal.io/83726f247fbe413093eac0b5c2ce65ea/algorand/indexer/'
    rate_limit = 0
    instance = None
    parser = AlgoNodeAlgorandResponseParser


class BlockDaemonAlgorandApi(AlgoNodeAlgorandApi):
    _base_url = 'https://svc.blockdaemon.com/algorand/mainnet/native/indexer/'
    rate_limit = 0
    instance = None
    parser = AlgoNodeAlgorandResponseParser
    USE_PROXY = True

    @classmethod
    def get_headers(cls):
        return {
            'Authorization': f'Bearer {cls.get_api_key()}',
        }

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.BLOCK_DAEMON_API_KEY)
