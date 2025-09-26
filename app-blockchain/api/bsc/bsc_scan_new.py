import random

from django.conf import settings
from exchange.base.models import Currencies
from exchange.blockchain.contracts_conf import BEP20_contract_currency, BEP20_contract_info
from exchange.blockchain.api.commons.blockscan import BlockScanAPI, BlockScanResponseParser


class BSCBlockScanParser(BlockScanResponseParser):
    precision = 18
    currency = Currencies.bnb
    symbol = 'BNB'

    @classmethod
    def contract_currency_list(cls):
        return BEP20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return BEP20_contract_info.get(cls.network_mode)


class BSCBlockScanAPI(BlockScanAPI):
    # API docs: https://bscscan.com/apis
    parser = BSCBlockScanParser
    symbol = 'BNB'
    cache_key = 'bsc'
    rate_limit = 0.2
    testnet_url = 'https://api-testnet.bscscan.com'
    chain_id = 56

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.BSCSCAN_API_KEY)
