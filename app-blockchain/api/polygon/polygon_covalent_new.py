import random
from decimal import Decimal
from django.conf import settings
from exchange.base.models import Currencies
from exchange.blockchain.contracts_conf import polygon_ERC20_contract_info, polygon_ERC20_contract_currency
from exchange.blockchain.api.commons.covalenthq import CovalenthqApi, CovalenthqResponseParser, \
    CovalenthqResponseValidator


class PolygonCovalentValidator(CovalenthqResponseValidator):
    min_valid_tx_amount = Decimal('0')

    @classmethod
    def validate_address_tx_transaction(cls, transaction):
        key2check = ['value', 'successful']
        for key in key2check:
            if transaction.get(key) is None:
                return False
        value = int(transaction.get('value'))
        log_events = transaction.get('log_events')
        if transaction.get('successful') and value > cls.min_valid_tx_amount and len(log_events) == 2:
            for log_event in log_events:
                if log_event.get('sender_address') != '0x0000000000000000000000000000000000001010':
                    return False
                if log_event.get('sender_name') != 'Matic Token':
                    return False
                if log_event.get('sender_contract_ticker_symbol') != 'MATIC':
                    return False
                if log_event.get('sender_contract_decimals') != 18:
                    return False
            return True
        return False


class PolygonCovalentParser(CovalenthqResponseParser):
    validator = PolygonCovalentValidator
    precision = 18
    currency = Currencies.pol
    symbol = 'MATIC'

    @classmethod
    def contract_currency_list(cls):
        return polygon_ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return polygon_ERC20_contract_info.get(cls.network_mode)


class PolygonCovalentAPI(CovalenthqApi):
    parser = PolygonCovalentParser
    _base_url = 'https://api.covalenthq.com/v1/137'
    testnet_url = 'https://api.covalenthq.com/v1/80001'
    symbol = 'MATIC'
    cache_key = 'matic'
    currency = Currencies.pol

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.COVALENT_API_KEYS)
