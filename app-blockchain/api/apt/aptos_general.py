from django.conf import settings
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class AptosParser(ResponseParser):
    precision = 8
    symbol = 'APT'
    EXPECTED_ADDRESS_LENGTH = 64
    currency = Currencies.apt

    @classmethod
    def unify_address(cls, address):
        if address and type(address) is str:
            if address.startswith('0x'):
                address = address[2:]
            padded_address = address.rjust(cls.EXPECTED_ADDRESS_LENGTH, '0')
            return '0x' + padded_address
        return address


class AptosGeneral(GeneralApi):
    currency = Currencies.apt
    cache_key = 'apt'
    symbol = 'APT'
    instance = None

    @classmethod
    def unpad_address(cls, address):
        if address and type(address) is str:
            if address.startswith('0x'):
                address = address[2:]
            padded_address = address.lstrip('0')
            return '0x' + padded_address
        return address

    @classmethod
    def get_address_txs(cls, address, **kwargs):
        address = cls.unpad_address(address)
        response = cls.request(request_method='get_address_txs', body=cls.get_address_txs_body(address),
                               headers=cls.get_headers(), address=address, apikey=cls.get_api_key())
        return response
