import random
from django.conf import settings
from exchange.base.models import Currencies
from exchange.blockchain.contracts_conf import BEP20_contract_currency, BEP20_contract_info
from exchange.blockchain.api.commons.covalenthq import CovalenthqApi, CovalenthqResponseParser, \
    CovalenthqResponseValidator


class BSCCovalentParser(CovalenthqResponseParser):
    validator = CovalenthqResponseValidator
    symbol = 'BNB'
    currency = Currencies.bnb
    precision = 18

    @classmethod
    def contract_currency_list(cls):
        return BEP20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return BEP20_contract_info.get(cls.network_mode)


class BSCCovalentApi(CovalenthqApi):
    parser = BSCCovalentParser
    symbol = 'BNB'
    cache_key = 'bsc'
    _base_url = 'https://api.covalenthq.com/v1/bsc-mainnet'
    testnet_url = 'https://api.covalenthq.com/v1/97'

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.COVALENT_API_KEYS)
