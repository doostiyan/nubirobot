import random

from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.contracts_conf import polygon_ERC20_contract_info, polygon_ERC20_contract_currency
from exchange.blockchain.api.commons.blockscan import BlockScanAPI, BlockScanResponseParser, BlockScanResponseValidator


class PolygonBlockScanParser(BlockScanResponseParser):
    symbol = 'MATIC'
    precision = 18
    currency = Currencies.pol

    @classmethod
    def contract_currency_list(cls):
        return polygon_ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return polygon_ERC20_contract_info.get(cls.network_mode)


class PolygonBlockScanAPI(BlockScanAPI):
    parser = PolygonBlockScanParser
    symbol = 'MATIC'
    cache_key = 'matic'
    rate_limit = 0.2  # 5 req/sec
    testnet_url = 'https://mumbai.polygonscan.com'
    # USE_PROXY = True
    chain_id = 137

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.POLYGANSCAN_API_KEY)
