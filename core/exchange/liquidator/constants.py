from decimal import Decimal

from django.conf import settings

from exchange.base.models import RIAL, TETHER

MAX_IN_MARKET_ORDER = {
    RIAL: Decimal('5_000_000_000_0'),
    TETHER: Decimal('1000'),
}

FEE_RATE = Decimal('0')
TOLERANCE_ORDER_PRICE = Decimal('0.02')
TOLERANCE_MARK_PRICE = Decimal('0.01')
USDT_TOLERANCE_ORDER_PRICE = Decimal('0.005')  # temporary until setting better mark price

LIQUIDATOR_EXTERNAL_CURRENCIES = set()
MAX_ORDER = {currency: v * Decimal('0.9') for currency, v in settings.NOBITEX_OPTIONS['maxOrders']['spot'].items()}

EXTERNAL_ORDER_USDT_VALUE_THRESHOLD = Decimal('5')

PENDING_LIQUIDATION_REQUESTS_FETCH_LIMIT = 100
