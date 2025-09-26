import random

from exchange import settings
from decimal import Decimal
from exchange.blockchain.api.algorand.algorand_algoexplorer import AlgoExplorerAlgorandApi, \
    AlgoExplorerAlgorandResponseParser, AlgoExplorerAlgorandValidator

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class PureStakeAlgorandValidator(AlgoExplorerAlgorandValidator):
    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        if transaction.get('genesis-hash') != 'wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=':
            return False
        return super().validate_transaction(transaction)


class PureStakeAlgorandResponseParser(AlgoExplorerAlgorandResponseParser):
    validator = PureStakeAlgorandValidator
    symbol = 'ALGO'
    currency = Currencies.algo
    precision = 6


class PureStakeAlgorandApi(AlgoExplorerAlgorandApi):
    # pure_stake sometimes return message forbidden
    _base_url = 'https://mainnet-algorand.api.purestake.io/idx2/'
    rate_limit = 0.1  # 10 rps
    instance = None
    SUPPORT_BATCH_GET_BLOCKS = True
    parser = PureStakeAlgorandResponseParser

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.PURESTAKE_API_KEYS)

    @classmethod
    def get_headers(cls):
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.get_api_key()
        }
