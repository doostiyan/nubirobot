from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from exchange.base.models import Currencies
from exchange.market.models import Market, Order
from exchange.pool.crons import DelegationLimitsCron
from exchange.pool.models import DelegationLimit, LiquidityPool


class DelegationLimitsCronTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.liquidity_pool = LiquidityPool.objects.create(
            currency=Currencies.btc,
            capacity=10,
            manager_id=410,
            is_active=True,
        )
        cls.market = Market.by_symbol('BTCUSDT')

    @patch('exchange.market.markprice.MarkPriceCalculator.get_mark_price', return_value=Decimal('10'))
    @patch(
        'exchange.pool.crons.get_market_liquidity_both_sides_depth',
        return_value={
            (Currencies.btc, Currencies.usdt): {
                'bids': Decimal('5'),
                'asks': Decimal('4'),
            },
        },
    )
    def test_bulk_create_creates_and_calculates(self, *_):
        DelegationLimitsCron().run()

        assert DelegationLimit.objects.count() == 7 * 2 * 9

        short_lvl0_1x = DelegationLimit.objects.get(
            vip_level=0,
            leverage=Decimal('1.0'),
            market=self.market,
            order_type=Order.ORDER_TYPES.sell,
        )
        assert short_lvl0_1x.limitation == Decimal('0.4')

        short_lvl4_3_5x = DelegationLimit.objects.get(
            vip_level=4,
            leverage=Decimal('3.5'),
            market=self.market,
            order_type=Order.ORDER_TYPES.sell,
        )
        assert short_lvl4_3_5x.limitation == Decimal('2.38')

        short_lvl6_5x = DelegationLimit.objects.get(
            vip_level=6,
            leverage=Decimal('5'),
            market=self.market,
            order_type=Order.ORDER_TYPES.sell,
        )
        assert short_lvl6_5x.limitation == Decimal('2.5')

        long_lvl0_1x = DelegationLimit.objects.get(
            vip_level=0,
            leverage=Decimal('1.0'),
            market=self.market,
            order_type=Order.ORDER_TYPES.buy,
        )
        assert long_lvl0_1x.limitation == Decimal('3.2')

        long_lvl4_3_5x = DelegationLimit.objects.get(
            vip_level=4,
            leverage=Decimal('3.5'),
            market=self.market,
            order_type=Order.ORDER_TYPES.buy,
        )
        assert long_lvl4_3_5x.limitation == Decimal('19.1')

        long_lvl6_5x = DelegationLimit.objects.get(
            vip_level=6,
            leverage=Decimal('5'),
            market=self.market,
            order_type=Order.ORDER_TYPES.buy,
        )
        assert long_lvl6_5x.limitation == Decimal('20')

    @patch('exchange.market.markprice.MarkPriceCalculator.get_mark_price', return_value=Decimal('10'))
    @patch(
        'exchange.pool.crons.get_market_liquidity_both_sides_depth',
        return_value={
            (Currencies.btc, Currencies.usdt): {
                'bids': Decimal('5'),
                'asks': Decimal('4'),
            },
        },
    )
    def test_bulk_create_updates_existing(self, *_):
        cron_job = DelegationLimitsCron()
        cron_job.run()

        assert DelegationLimit.objects.count() == 7 * 2 * 9

        target = DelegationLimit.objects.get(
            vip_level=0,
            leverage=Decimal('1.0'),
            market=self.market,
            order_type=Order.ORDER_TYPES.buy,
        )
        target.limitation = Decimal('999')
        target.save()

        self.market.max_leverage = Decimal('6')
        self.market.save()
        cron_job.run()

        assert DelegationLimit.objects.count() == 7 * 2 * 11

        target.refresh_from_db()
        assert target.limitation == Decimal('3.2')

        new_limit_3_5_5x = DelegationLimit.objects.get(
            vip_level=3,
            leverage=Decimal('5.5'),
            market=self.market,
            order_type=Order.ORDER_TYPES.buy,
        )
        assert new_limit_3_5_5x.limitation == Decimal('9.45')

    @patch('exchange.market.markprice.MarkPriceCalculator.get_mark_price', return_value=Decimal('100'))
    @patch(
        'exchange.pool.crons.get_market_liquidity_both_sides_depth',
        return_value={
            (Currencies.btc, Currencies.usdt): {
                'bids': Decimal('5'),
                'asks': Decimal('4'),
            },
        },
    )
    def test_delegation_limit_precisions(self, *_):
        DelegationLimitsCron().run()

        short_lvl4_3_5x = DelegationLimit.objects.get(
            vip_level=4,
            leverage=Decimal('3.5'),
            market=self.market,
            order_type=Order.ORDER_TYPES.sell,
        )
        assert short_lvl4_3_5x.limitation == Decimal('2.38')

        long_lvl4_3_5x = DelegationLimit.objects.get(
            vip_level=4,
            leverage=Decimal('3.5'),
            market=self.market,
            order_type=Order.ORDER_TYPES.buy,
        )
        assert long_lvl4_3_5x.limitation == Decimal('191')
