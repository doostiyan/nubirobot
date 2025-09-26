import random

from exchange import settings
from exchange.blockchain.api.algorand.algorand_algoexplorer import AlgoExplorerAlgorandApi, \
    AlgoExplorerAlgorandResponseParser, AlgoExplorerAlgorandValidator
from decimal import Decimal

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class BloqCloudAlgorandValidator(AlgoExplorerAlgorandValidator):
    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        if transaction.get('genesis-hash') != 'wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=':
            return False
        return super().validate_transaction(transaction)


class BloqCloudAlgorandResponseParser(AlgoExplorerAlgorandResponseParser):
    validator = BloqCloudAlgorandValidator
    symbol = 'ALGO'
    currency = Currencies.algo
    precision = 6


class BloqCloudAlgorandApi(AlgoExplorerAlgorandApi):
    _base_url = 'https://algorand.connect.bloq.cloud/indexer/'
    rate_limit = 9  # 10000 request per day
    instance = None
    SUPPORT_BATCH_GET_BLOCKS = True
    parser = BloqCloudAlgorandResponseParser

    @classmethod
    def get_api_key(cls):
        api_key = random.choice(settings.BLOQ_CLOUD_API_KEYS)
        return api_key

    @classmethod
    def get_headers(cls):
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.get_api_key()
        }
