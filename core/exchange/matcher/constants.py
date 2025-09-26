"""Matcher Constants"""

from decimal import Decimal

from exchange.base.models import PRICE_PRECISIONS

MIN_PRICE_PRECISION = min(PRICE_PRECISIONS.values())

STOPLOSS_ACTIVATION_MARK_PRICE_GUARD_RATE = Decimal('0.01')

SERIAL_MARKET_SYMBOLS = ('USDTIRT',)
