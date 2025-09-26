from decimal import Decimal

from django.conf import settings


LIQUIDATION_MARK_PRICE_GUARD_RATE = Decimal('0.01')
SETTLEMENT_ORDER_PRICE_RANGE_RATE = Decimal('0.02')  # to have less chance of failure
SETTLEMENT_ORDER_PRICE_MARK_PRICE_GUARD_RATE = Decimal('0.01')  # to avoid shadows
USDT_SETTLEMENT_PRICE_RANGE_RATE = Decimal('0.005')  # temporary until setting better mark price
