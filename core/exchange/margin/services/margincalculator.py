import dataclasses
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_UP, Decimal
from typing import Iterable, Optional

from django.conf import settings
from django.utils.functional import cached_property

from exchange.base.constants import ZERO
from exchange.base.helpers import get_max_db_value
from exchange.liquidator.models import LiquidationRequest
from exchange.margin.models import Position, PositionFee
from exchange.market.models import Market, Order


@dataclass
class MarginCalculator:
    side: int
    leverage: Decimal
    entry_price: Decimal
    extension_days: int
    trade_fee_rate: Decimal

    def get_pnl(self, exit_price: Decimal, amount: Decimal) -> Decimal:
        if self.side == Position.SIDES.sell:
            liability = amount / (1 - self.trade_fee_rate)
            total_pnl = self.entry_price * amount * (1 - self.trade_fee_rate) - exit_price * liability
        else:
            liability = amount * (1 - self.trade_fee_rate)
            total_pnl = exit_price * liability * (1 - self.trade_fee_rate) - self.entry_price * amount
        return total_pnl * Position.get_user_share(self.extension_days, profit=total_pnl > 0)

    def get_pnl_percent(self, pnl: Decimal, amount: Decimal) -> Decimal:
        return pnl * self.leverage / (self.entry_price * amount) * 100

    def get_exit_price(self, pnl_percent: int) -> Decimal:
        pnl_ratio = pnl_percent * Decimal('0.01') / self.leverage
        if pnl_ratio > 0:
            pnl_ratio /= Position.get_user_share(self.extension_days, profit=pnl_ratio > 0)
        if self.side == Position.SIDES.sell:
            exit_price = self.entry_price * (1 - self.trade_fee_rate - pnl_ratio) * (1 - self.trade_fee_rate)
        else:
            exit_price = self.entry_price * (1 + pnl_ratio) / (1 - self.trade_fee_rate) ** 2
        return exit_price

    def get_liquidation_price(self, market: Market, amount: Decimal, added_collateral: Decimal) -> Decimal:
        collateral = self.entry_price * amount / self.leverage + added_collateral
        if self.extension_days:
            extension_fee = PositionFee.get_amount(
                market.src_currency, market.dst_currency, self.side, self.entry_price * amount
            )
            collateral -= extension_fee * self.extension_days
        if self.side == Position.SIDES.sell:
            earned_amount = self.entry_price * amount * (1 - self.trade_fee_rate)
            liability = amount / (1 - self.trade_fee_rate)
            liquidation_price = (earned_amount + collateral) / liability / settings.MAINTENANCE_MARGIN_RATIO
        else:
            liability = amount * (1 - self.trade_fee_rate)
            liquidation_price = (self.entry_price * amount * settings.MAINTENANCE_MARGIN_RATIO - collateral) / liability
        return max(liquidation_price, ZERO)


@dataclasses.dataclass
class ExchangedItem:
    side: int
    amount: Decimal
    total_price: Decimal

    @classmethod
    def from_order(cls, order: Order) -> 'ExchangedItem':
        return ExchangedItem(
            side=order.order_type,
            amount=order.matched_amount,
            total_price=order.matched_total_price,
        )

    @classmethod
    def from_liquidation_request(cls, liquidation_request: LiquidationRequest) -> 'ExchangedItem':
        return ExchangedItem(
            side=liquidation_request.side,
            amount=liquidation_request.filled_amount,
            total_price=liquidation_request.net_total_price,
        )


class MarginSideCalculator:
    def __init__(self, position: Position):
        self.position = position

    @cached_property
    def market_price(self) -> Decimal:
        return self.position.market.get_last_trade_price() or ZERO

    def get_total_asset(self) -> Decimal:
        raise NotImplementedError

    def get_liability(self) -> Decimal:
        raise NotImplementedError

    def get_order_blocking_price(self, order: Order) -> Decimal:
        raise NotImplementedError

    def get_unmatched_total_amount(self):
        return sum((order.unmatched_amount for order in self.position.open_side_orders if order.blocks_balance), ZERO)

    def get_system_settled_amount(self) -> Decimal:
        return sum(
            (
                -liq_quest.filled_amount if liq_quest.is_sell else liq_quest.filled_amount
                for liq_quest in self.position.cached_liquidation_requests
            ),
            start=ZERO,
        )

    def get_system_settled_total_price(self) -> Decimal:
        return sum(
            (
                (liq_quest.filled_total_price if liq_quest.is_sell else -liq_quest.filled_total_price) - liq_quest.fee
                for liq_quest in self.position.cached_liquidation_requests
            ),
            start=ZERO,
        )

    def get_unmatched_total_price(self):
        return sum(
            (
                order.unmatched_amount * self.get_order_blocking_price(order)
                for order in self.position.open_side_orders
                if order.blocks_balance
            ),
            ZERO,
        )

    def get_exchanged_items_average_price(self, items: Iterable[ExchangedItem]) -> Optional[Decimal]:
        total_amount = sum(item.amount for item in items)
        if not total_amount:
            return None
        total_price = sum((item.total_price for item in items), ZERO)
        precision = self.position.market.price_precision
        return (total_price / total_amount).quantize(precision)

    def get_entry_price(self):
        return self.get_exchanged_items_average_price(
            [ExchangedItem.from_order(order) for order in self.position.open_side_orders]
        )

    def get_exit_price(self):
        return self.get_exchanged_items_average_price(
            [ExchangedItem.from_order(order) for order in self.position.close_side_orders]
            + [
                ExchangedItem.from_liquidation_request(liq_quest)
                for liq_quest in self.position.cached_liquidation_requests
            ]
        )

    def get_delegation_total_price(self) -> Decimal:
        raise NotImplementedError

    def get_total_pnl_percent(self, exit_price: Decimal) -> Decimal:
        raise NotImplementedError

    def get_unrealized_total_pnl(self) -> Decimal:
        raise NotImplementedError

    def get_liquidation_price(self, precision: Decimal) -> Decimal:
        raise NotImplementedError

    def get_margin_ratio(self) -> Decimal:
        raise NotImplementedError


class ShortCalculator(MarginSideCalculator):
    def get_total_asset(self) -> Decimal:
        return self.position.collateral + self.position.earned_amount

    def get_liability(self) -> Decimal:
        value = self.position.delegated_amount / (1 - self.position.trade_fee_rate)
        return value.quantize(Decimal('1E-10'), ROUND_UP)

    def get_order_blocking_price(self, order: Order) -> Decimal:
        return max(order.price, self.market_price)

    def get_delegation_total_price(self) -> Decimal:
        total_price = self.get_unmatched_total_price()
        if self.position.delegated_amount:
            total_price += self.position.delegated_amount * self.position.entry_price
        return total_price

    def get_total_pnl_percent(self, exit_price) -> Decimal:
        price_change_ratio = exit_price / self.position.entry_price / (1 - self.position.trade_fee_rate) ** 2
        return (1 - price_change_ratio) * self.position.leverage * 100

    def get_unrealized_total_pnl(self) -> Decimal:
        return self.position.earned_amount - self.position.liability * self.market_price

    def get_liquidation_price(self, precision: Decimal) -> Decimal:
        value = self.position.total_asset / self.position.liability / settings.MAINTENANCE_MARGIN_RATIO
        max_value = get_max_db_value(Position.liquidation_price).quantize(precision, rounding=ROUND_DOWN)
        return min(value.quantize(precision), max_value)

    def get_margin_ratio(self) -> Optional[Decimal]:
        total_amount = self.position.liability + self.get_unmatched_total_amount()
        if not total_amount:
            return None
        total_asset = self.position.total_asset + self.get_unmatched_total_price()
        return total_asset / (total_amount * self.market_price)


class LongCalculator(MarginSideCalculator):
    def get_total_asset(self) -> Decimal:
        return self.position.collateral + self.position.delegated_amount * self.market_price

    def get_liability(self) -> Decimal:
        return self.position.delegated_amount

    def get_order_blocking_price(self, order: Order) -> Decimal:
        return order.price or self.market_price

    def get_delegation_total_price(self) -> Decimal:
        total_price = self.get_unmatched_total_price()
        if self.position.earned_amount < 0:
            total_price -= self.position.earned_amount
        return total_price

    def get_total_pnl_percent(self, exit_price) -> Decimal:
        price_change_ratio = exit_price / self.position.entry_price * (1 - self.position.trade_fee_rate) ** 2
        return (price_change_ratio - 1) * self.position.leverage * 100

    def get_unrealized_total_pnl(self) -> Decimal:
        return self.position.earned_amount + self.position.liability * self.market_price * (
            1 - self.position.trade_fee_rate
        )

    def get_liquidation_price(self, precision: Decimal) -> Decimal:
        value = (
            -self.position.earned_amount * settings.MAINTENANCE_MARGIN_RATIO - self.position.collateral
        ) / self.position.liability
        return max(value.quantize(precision), ZERO)

    def get_margin_ratio(self) -> Optional[Decimal]:
        delegation_total_price = self.get_delegation_total_price()
        if not delegation_total_price:
            return Decimal('Inf')
        total_asset = self.position.total_asset + self.get_unmatched_total_price()
        return total_asset / delegation_total_price
