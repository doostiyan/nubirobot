from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase

from exchange.base.models import Settings
from exchange.margin.models import Position
from exchange.margin.services import MarginManager
from exchange.market.markprice import MarkPriceCalculator
from exchange.market.models import Order
from tests.margin.test_positions import PositionTestMixin


class PositionSettlementOrderTest(PositionTestMixin, TestCase):
    @classmethod
    def open_position(cls, side, status, leverage, amount, entry_price):
        position = Position.objects.create(
            src_currency=cls.market.src_currency,
            dst_currency=cls.market.dst_currency,
            user=cls.user,
            side=side,
            status=status,
            leverage=Decimal(leverage),
            collateral=Decimal(amount) * Decimal(entry_price) / Decimal(leverage),
            delegated_amount=Decimal(amount),
            entry_price=Decimal(entry_price),
        )
        order = Order.objects.create(
            src_currency=position.src_currency,
            dst_currency=position.dst_currency,
            user=position.user,
            order_type=side,
            status=Order.STATUS.done,
            amount=amount,
            price=entry_price,
            matched_amount=amount,
        )
        position.orders.add(order, through_defaults={'blocked_collateral': position.collateral})
        return position

    def _enable_markets_in_liquidator(self, market_symbols):
        Settings.set('liquidator_enabled_markets', market_symbols)

    def test_sell_position_settlement_in_liquidator(self):
        self._enable_markets_in_liquidator('["BTCUSDT"]')

        self.src_pool.get_dst_wallet(self.market.dst_currency).create_transaction('manual', 200).commit()
        position = self.open_position(Position.SIDES.sell, Position.STATUS.liquidated, 3, '0.001', '66000')
        MarginManager.settle_position_in_system(position.id)
        liquidation_request = position.liquidation_requests.last()
        assert liquidation_request
        assert liquidation_request.amount == position.delegated_amount
        assert liquidation_request.side == liquidation_request.SIDES.buy
        assert liquidation_request.src_wallet == self.src_pool.src_wallet
        assert liquidation_request.dst_wallet == self.src_pool.get_dst_wallet(self.market.dst_currency)
        assert liquidation_request.is_open

    def test_buy_position_settlement_in_liquidator(self):
        self._enable_markets_in_liquidator('["BTCUSDT"]')

        self.dst_pool.get_dst_wallet(self.market.src_currency).create_transaction('manual', '0.001').commit()
        position = self.open_position(Position.SIDES.buy, Position.STATUS.liquidated, 2, '0.001', '66000')
        MarginManager.settle_position_in_system(position.id)
        liquidation_request = position.liquidation_requests.last()
        assert liquidation_request
        assert liquidation_request.amount == position.delegated_amount
        assert liquidation_request.side == liquidation_request.SIDES.sell
        assert liquidation_request.src_wallet == self.dst_pool.get_dst_wallet(self.market.src_currency)
        assert liquidation_request.dst_wallet == self.dst_pool.src_wallet
        assert liquidation_request.is_open

    def test_sell_position_settlement_in_market_lower_than_mark_price(self):
        self.src_pool.get_dst_wallet(self.market.dst_currency).create_transaction('manual', 200).commit()
        position = self.open_position(Position.SIDES.sell, Position.STATUS.liquidated, 3, '0.001', '66000')
        self.set_market_price(Decimal('80_000'), self.MARKET_SYMBOL)
        cache.set(MarkPriceCalculator.CACHE_KEY.format(src_currency=self.market.src_currency), Decimal('83_000'))
        MarginManager.settle_position_in_system(position.id)
        assert not position.liquidation_requests.exists()
        settlement_orders = position.orders.filter(channel=Order.CHANNEL.system_margin)
        assert len(settlement_orders) == 1
        settlement_order = settlement_orders[0]
        assert settlement_order.is_buy
        assert settlement_order.is_active
        assert settlement_order.amount == position.liability
        assert settlement_order.price == Decimal('81_600')

    def test_sell_position_settlement_in_market_close_to_mark_price(self):
        self.src_pool.get_dst_wallet(self.market.dst_currency).create_transaction('manual', 200).commit()
        position = self.open_position(Position.SIDES.sell, Position.STATUS.liquidated, 3, '0.001', '66000')
        self.set_market_price(Decimal('80_000'), self.MARKET_SYMBOL)
        cache.set(MarkPriceCalculator.CACHE_KEY.format(src_currency=self.market.src_currency), Decimal('80_500'))
        MarginManager.settle_position_in_system(position.id)
        assert not position.liquidation_requests.exists()
        settlement_orders = position.orders.filter(channel=Order.CHANNEL.system_margin)
        assert len(settlement_orders) == 1
        settlement_order = settlement_orders[0]
        assert settlement_order.is_buy
        assert settlement_order.is_active
        assert settlement_order.amount == position.liability
        assert settlement_order.price == Decimal('81305')

    def test_buy_position_settlement_in_market_close_to_mark_price(self):
        self.dst_pool.get_dst_wallet(self.market.src_currency).create_transaction('manual', '0.001').commit()
        position = self.open_position(Position.SIDES.buy, Position.STATUS.liquidated, 2, '0.001', '66000')
        self.set_market_price(Decimal('50_000'), self.MARKET_SYMBOL)
        cache.set(MarkPriceCalculator.CACHE_KEY.format(src_currency=self.market.src_currency), Decimal('49_500'))
        MarginManager.settle_position_in_system(position.id)
        assert not position.liquidation_requests.exists()
        settlement_orders = position.orders.filter(channel=Order.CHANNEL.system_margin)
        assert len(settlement_orders) == 1
        settlement_order = settlement_orders[0]
        assert settlement_order.is_sell
        assert settlement_order.is_active
        assert settlement_order.amount == position.liability
        assert settlement_order.price == Decimal('49_005')

    def test_buy_position_settlement_in_market_higher_than_mark_price(self):
        self.dst_pool.get_dst_wallet(self.market.src_currency).create_transaction('manual', '0.001').commit()
        position = self.open_position(Position.SIDES.buy, Position.STATUS.liquidated, 2, '0.001', '66000')
        self.set_market_price(Decimal('50_000'), self.MARKET_SYMBOL)
        cache.set(MarkPriceCalculator.CACHE_KEY.format(src_currency=self.market.src_currency), Decimal('47_000'))
        MarginManager.settle_position_in_system(position.id)
        assert not position.liquidation_requests.exists()
        settlement_orders = position.orders.filter(channel=Order.CHANNEL.system_margin)
        assert len(settlement_orders) == 1
        settlement_order = settlement_orders[0]
        assert settlement_order.is_sell
        assert settlement_order.is_active
        assert settlement_order.amount == position.liability
        assert settlement_order.price == Decimal('49_000')

    def tearDown(self):
        MarkPriceCalculator.delete_mark_price(self.market.src_currency)
        self.set_market_price(self.MARKET_PRICE, self.MARKET_SYMBOL)

        Settings.set('liquidator_enabled_markets', '[]')
