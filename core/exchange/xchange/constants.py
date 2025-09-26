from decimal import Decimal

from exchange.accounts.models import UserRestriction
from exchange.xchange.models import ExchangeTrade

GET_MISSED_CONVERSION_STATUS_RETRIES = 4
GET_MISSED_CONVERSION_STATUS_COUNTDOWN = 5
ALL_XCHANGE_PAIRS_CACHE_KEY = 'xchange_all_currency_pairs'
XCHANGE_PAIR_PRICES_CACHE_KEY = 'xchange_pair_price_{currency}_{to_currency}'
RESTRICTIONS = {UserRestriction.RESTRICTION.Trading, UserRestriction.RESTRICTION.Convert}


USER_AGENT_MAP = {
    'android': {
        'lite': ExchangeTrade.USER_AGENT.android_lite,
        'pro': ExchangeTrade.USER_AGENT.android_pro,
        'default': ExchangeTrade.USER_AGENT.android,
    },
    'iosapp': ExchangeTrade.USER_AGENT.ios,
    'python-requests': ExchangeTrade.USER_AGENT.api,
    'restsharp': ExchangeTrade.USER_AGENT.api,
    'guzzlehttp': ExchangeTrade.USER_AGENT.api,
    'python': ExchangeTrade.USER_AGENT.api,
    'axios': ExchangeTrade.USER_AGENT.api,
    'mozilla': ExchangeTrade.USER_AGENT.mozilla,
    'opera': ExchangeTrade.USER_AGENT.opera,
    'safari': ExchangeTrade.USER_AGENT.safari,
    'edge': ExchangeTrade.USER_AGENT.edge,
    'chrome': ExchangeTrade.USER_AGENT.chrome,
    'firefox': ExchangeTrade.USER_AGENT.firefox,
    'samsung internet': ExchangeTrade.USER_AGENT.samsung_internet,
}

SMALL_ASSET_BATCH_CONVERT_MAX_AMOUNT_THRESHOLD_RATIO = Decimal('0.9')
UPDATE_SMALL_ASSET_CONVERT_STATUS_COUNTDOWN = 3600
