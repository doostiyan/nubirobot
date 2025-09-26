from django.conf import settings

from exchange.config.config.data import CURRENCY_INFO
from exchange.config.config.models import Currencies

if settings.IS_TESTNET:
    CURRENCY_INFO[Currencies.btc]['network_list']['BTC']['address_regex'] = '^[2mn][a-km-zA-HJ-NP-Z1-9]{25,34}$|^(tb1)[0-9A-Za-z]{39,59}$'
    CURRENCY_INFO[Currencies.dot]['network_list']['DOT']['address_regex'] = '(5)[0-9a-z-A-Z]{44,50}$'
