from decimal import Decimal

from exchange.market.markprice import MarkPriceCalculator
from exchange.staking.errors import MarkPriceNotAvailableError


class PriceProvider:
    def __init__(self, src_currency: int, dst_currency: int):
        self.src_currency = src_currency
        self.dst_currency = dst_currency

    def get_mark_price(self) -> Decimal:
        if self.src_currency == self.dst_currency:
            return Decimal('1.0')

        mark_price = MarkPriceCalculator.get_mark_price(self.src_currency, self.dst_currency)

        if not mark_price:
            raise MarkPriceNotAvailableError()
        return mark_price
