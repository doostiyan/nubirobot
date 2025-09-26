"""Market Constants"""
from decimal import Decimal

from django.conf import settings

from exchange.base.models import PRICE_PRECISIONS
from exchange.wallet.constants import TRANSACTION_MAX_DIGITS

MIN_PRICE_PRECISION = min(PRICE_PRECISIONS.values())

# Field sizes

ORDER_MAX_DIGITS = TRANSACTION_MAX_DIGITS
assert ORDER_MAX_DIGITS <= TRANSACTION_MAX_DIGITS

FEE_MAX_DIGITS = ORDER_MAX_DIGITS - 2  # i.e. at most 1%

TOTAL_VOLUME_MAX_DIGITS = ORDER_MAX_DIGITS + 6  # i.e. 1 million max orders per day

# Logical
MARKET_ORDER_MAX_PRICE_DIFF = Decimal('0.1')

SYSTEM_USERS_VIP_LEVEL = 0
