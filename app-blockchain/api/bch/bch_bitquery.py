import random
from decimal import Decimal
from cashaddress import convert
from cashaddress.convert import InvalidAddress
from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.commons.bitquery import (BitqueryApi,
                                                      BitqueryResponseParser,
                                                      BitqueryValidator)


class BitcoinCashBitqueryValidator(BitqueryValidator):
    min_valid_tx_amount = Decimal('0.003')


class BitcoinCashBitqueryResponseParser(BitqueryResponseParser):
    currency = Currencies.bch
    validator = BitcoinCashBitqueryValidator
    symbol = 'BCH'

    @classmethod
    def convert_address(cls, address):
        try:
            cash_address = 'bitcoincash:' + address
            return convert.to_legacy_address(cash_address)
        except InvalidAddress:
            return None


class BitcoinCashBitqueryAPI(BitqueryApi):
    """
        coins: BCH
        API docs: https://graphql.bitquery.io/ide
        Explorer: https://explorer.bitquery.io/ltc
    """
    symbol = 'BCH'
    cache_key = 'bch'
    currency = Currencies.bch
    parser = BitcoinCashBitqueryResponseParser
    GET_BLOCK_ADDRESSES_MAX_NUM = 2
    BITQUERY_NETWORK = 'bitcash'

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.BITQUERY_API_KEY)
