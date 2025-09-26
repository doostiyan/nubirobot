"""Generic Constants"""

import datetime
from decimal import Decimal

ZERO = Decimal(0)

MAX_PRECISION = Decimal('1E-10')
MONETARY_DECIMAL_PLACES = -MAX_PRECISION.adjusted()

MIN_DATETIME = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)

MAX_POSITIVE_32_INT = 4_294_967_296
MAX_32_INT = 2_147_483_647
MIN_32_INT = -2_147_483_648

PRICE_GUARD_RANGE = Decimal('0.2')
