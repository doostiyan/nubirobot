from decimal import Decimal

from django.test import TestCase

from exchange.base.models import Currencies
from exchange.market.models import Order
from exchange.pool.crons import get_market_liquidity_both_sides_depth


class LiquidityDepthTestCase(TestCase):
    def create_order(
        self,
        src_currency,
        dst_currency,
        order_type,
        price,
        amount,
        matched_amount=Decimal('0'),
        status=Order.STATUS.active,
        execution_type=Order.EXECUTION_TYPES.limit,
    ):
        return Order.objects.create(
            user_id=201,
            src_currency=src_currency,
            dst_currency=dst_currency,
            order_type=order_type,
            price=price,
            amount=amount,
            matched_amount=matched_amount,
            status=status,
            execution_type=execution_type,
        )

    def test_excludes_orders_with_non_active_status_or_execution(self):
        self.create_order(
            Currencies.btc,
            Currencies.usdt,
            Order.ORDER_TYPES.buy,
            Decimal('100'),
            Decimal('10'),
            status=Order.STATUS.canceled,
        )
        self.create_order(
            Currencies.btc,
            Currencies.usdt,
            Order.ORDER_TYPES.buy,
            Decimal('100'),
            Decimal('20'),
            execution_type=Order.EXECUTION_TYPES.market,
        )
        liquidity_depths = get_market_liquidity_both_sides_depth()
        assert liquidity_depths == {}

    def test_basic_depth_inclusion_and_exclusion(self):
        self.create_order(Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.buy, Decimal('100'), Decimal('10'))
        self.create_order(Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.buy, Decimal('95'), Decimal('20'))
        self.create_order(Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.buy, Decimal('94'), Decimal('30'))
        self.create_order(Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.sell, Decimal('110'), Decimal('5'))
        self.create_order(Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.sell, Decimal('118'), Decimal('50'))

        liquidity_depths = get_market_liquidity_both_sides_depth()
        key = (Currencies.btc, Currencies.usdt)
        assert key in liquidity_depths
        assert liquidity_depths[key]['bids'] == Decimal('30')
        assert liquidity_depths[key]['asks'] == Decimal('5')

    def test_multiple_markets_separate_depths(self):
        self.create_order(Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.buy, Decimal('200'), Decimal('15'))
        self.create_order(Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.buy, Decimal('190'), Decimal('5'))
        self.create_order(Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.buy, Decimal('189'), Decimal('5'))

        self.create_order(Currencies.eth, Currencies.usdt, Order.ORDER_TYPES.buy, Decimal('50'), Decimal('100'))
        self.create_order(Currencies.eth, Currencies.usdt, Order.ORDER_TYPES.buy, Decimal('47.5'), Decimal('50'))
        self.create_order(Currencies.eth, Currencies.usdt, Order.ORDER_TYPES.buy, Decimal('47'), Decimal('50'))

        liquidity_depths = get_market_liquidity_both_sides_depth()

        assert liquidity_depths[(Currencies.btc, Currencies.usdt)]['bids'] == Decimal('20')
        assert liquidity_depths[(Currencies.eth, Currencies.usdt)]['bids'] == Decimal('150')

    def test_multiple_markets_separate_depths_with_nonzero_matched_amount(self):
        self.create_order(
            Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.buy, Decimal('200'), Decimal('15'), Decimal('10')
        )
        self.create_order(
            Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.buy, Decimal('190'), Decimal('5'), Decimal('2')
        )
        self.create_order(
            Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.buy, Decimal('189'), Decimal('5'), Decimal('1')
        )

        self.create_order(
            Currencies.eth, Currencies.usdt, Order.ORDER_TYPES.buy, Decimal('50'), Decimal('100'), Decimal('99')
        )
        self.create_order(
            Currencies.eth, Currencies.usdt, Order.ORDER_TYPES.buy, Decimal('47.5'), Decimal('50'), Decimal('49')
        )
        self.create_order(
            Currencies.eth, Currencies.usdt, Order.ORDER_TYPES.buy, Decimal('47'), Decimal('50'), Decimal('49')
        )

        liquidity_depths = get_market_liquidity_both_sides_depth()

        assert liquidity_depths[(Currencies.btc, Currencies.usdt)]['bids'] == Decimal('8')
        assert liquidity_depths[(Currencies.eth, Currencies.usdt)]['bids'] == Decimal('2')

    def test_decimal_precision(self):
        price = Decimal('123.456789')
        self.create_order(Currencies.xrp, Currencies.usdt, Order.ORDER_TYPES.buy, price, Decimal('0.00012345'))
        liquidity_depths = get_market_liquidity_both_sides_depth()
        val = liquidity_depths[(Currencies.xrp, Currencies.usdt)]['bids']
        assert isinstance(val, Decimal)
        assert val == Decimal('0.00012345')
