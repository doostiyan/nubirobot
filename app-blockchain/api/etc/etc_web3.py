from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.commons.web3 import Web3ResponseParser, Web3Api, Web3ResponseValidator


class EtcWeb3ResponseParser(Web3ResponseParser):
    validator = Web3ResponseValidator

    symbol = 'ETC'
    currency = Currencies.etc
    precision = 18


class EtcWeb3Api(Web3Api):
    parser = EtcWeb3ResponseParser
    _base_url = 'https://etc.rivet.link/'
    cache_key = 'etc'
