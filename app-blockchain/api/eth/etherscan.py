import random

from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.commons.blockscan import (
    BlockScanAPI,
    BlockScanResponseParser,
    BlockScanResponseValidator
)
from exchange.blockchain.contracts_conf import ERC20_contract_info, ERC20_contract_currency


class EtherscanResponseParser(BlockScanResponseParser):
    validator = BlockScanResponseValidator
    symbol = 'ETH'
    currency = Currencies.eth

    @classmethod
    def contract_currency_list(cls):
        return ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return ERC20_contract_info.get(cls.network_mode)


class EtherscanAPI(BlockScanAPI):
    parser = EtherscanResponseParser
    testnet_url = 'https://api-ropsten.etherscan.io'
    cache_key = 'eth'
    chain_id = 1

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.ETHERSCAN_API_KEYS)
