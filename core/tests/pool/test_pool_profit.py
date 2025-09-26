from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import PropertyMock, patch

import jdatetime
import pytest
from django.core.cache import cache
from django.test import TestCase, override_settings

from exchange.accounts.models import User
from exchange.base.calendar import get_first_and_last_of_jalali_month, ir_now, ir_today, ir_tz
from exchange.base.models import Currencies
from exchange.margin.models import Position
from exchange.market.models import Order
from exchange.pool.crons import CalculateDailyPoolProfitsCron
from exchange.pool.errors import PartialConversionOrderException
from exchange.pool.functions import (
    distribute_profits_for_target_pools,
    populate_daily_profit_for_target_pools,
    populate_realized_profits_for_target_pools,
)
from exchange.pool.models import LiquidityPool, PoolProfit
from exchange.wallet.models import Wallet

USDT = Currencies.usdt
BTC = Currencies.btc
RLS = Currencies.rls
ETH = Currencies.eth
LTC = Currencies.ltc


@patch('exchange.base.calendar.ir_today', lambda: jdatetime.date(year=1400, month=12, day=1).togregorian())
@patch(
    'django.utils.timezone.now',
    lambda: datetime.combine(jdatetime.date(year=1400, month=12, day=1).togregorian(), datetime.min.time(), ir_tz()),
)
class PoolProfitTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.get(pk=201)
        self.btc_pool = LiquidityPool.objects.create(currency=BTC, capacity=2, manager_id=410, is_active=True, activated_at=ir_now())
        self.shib_pool = LiquidityPool.objects.create(
            currency=Currencies.shib, capacity=2, manager_id=411, is_active=True, activated_at=ir_now(), current_profit=100
        )
        self.usdt_pool = LiquidityPool.objects.create(
            currency=Currencies.usdt, capacity=1000, manager_id=413, is_active=True, activated_at=ir_now()
        )
        charge_tx = self.btc_pool.get_dst_wallet(USDT).create_transaction(tp='delegate', amount=1000000)
        charge_tx.commit()
        self.base_date = datetime.combine(
            jdatetime.date(year=1400, month=12, day=1).togregorian(), datetime.min.time(), ir_tz()
        )

        cache.set('orderbook_USDTIRT_best_active_buy', Decimal(2000))
        self.positions = [
            Position.objects.create(  # valid
                user=self.user1,
                src_currency=BTC,
                dst_currency=USDT,
                side=Position.SIDES.sell,
                collateral=213,
                earned_amount=2,
                pnl=1,
                closed_at=self.base_date - timedelta(days=1),
            ),
            Position.objects.create(  # valid
                user=self.user1,
                src_currency=BTC,
                dst_currency=USDT,
                side=Position.SIDES.sell,
                collateral=213,
                earned_amount=5,
                pnl=2,
                closed_at=self.base_date - timedelta(days=1),
            ),
            Position.objects.create(  # invalid
                user=self.user1,
                src_currency=ETH,
                dst_currency=USDT,
                side=Position.SIDES.sell,
                collateral=213,
                earned_amount=5,
                pnl=2,
                closed_at=self.base_date - timedelta(days=1),
            ),
            Position.objects.create(  # invalid
                user=self.user1,
                src_currency=BTC,
                dst_currency=RLS,
                side=Position.SIDES.sell,
                collateral=213,
                earned_amount=5,
                pnl=2,
                closed_at=self.base_date - timedelta(days=1),
            ),
            Position.objects.create(  # invalid
                user=self.user1,
                src_currency=BTC,
                dst_currency=USDT,
                side=Position.SIDES.sell,
                collateral=213,
                earned_amount=200,
                pnl=2,
                closed_at=self.base_date - timedelta(days=31),
            ),
            Position.objects.create(  # invalid
                user=self.user1,
                src_currency=BTC,
                dst_currency=USDT,
                side=Position.SIDES.sell,
                collateral=213,
                earned_amount=300,
                pnl=2,
                closed_at=self.base_date + timedelta(days=1),
            ),
        ]
        profit_wallet = Wallet.get_user_wallet(LiquidityPool.get_profit_collector(), USDT)
        profit_wallet.create_transaction(tp='pnl', amount=10).commit()

    def test_pools_profit(self):
        to_date = ir_today()
        from_date, _ = get_first_and_last_of_jalali_month(ir_today() - timedelta(days=1))
        pools_profit1 = PoolProfit.calc_pools_profit([self.btc_pool], from_date, to_date)
        assert len(pools_profit1) == 1
        btc_profits1 = pools_profit1[self.btc_pool.id]
        assert len(btc_profits1) == 2
        assert set(btc_profits1.keys()) == {RLS, USDT}
        assert btc_profits1[USDT].position_profit == 4
        assert btc_profits1[USDT].to_date == to_date
        assert btc_profits1[USDT].from_date == from_date

        Position.objects.create(
            user=self.user1,
            src_currency=BTC,
            dst_currency=USDT,
            side=Position.SIDES.sell,
            collateral=213,
            earned_amount=2,
            pnl=1,
            closed_at=self.base_date - timedelta(days=1),
        )

        pools_profit2 = PoolProfit.calc_pools_profit([self.btc_pool], from_date, to_date)
        btc_profits2 = pools_profit2[self.btc_pool.id]
        assert btc_profits2[USDT].position_profit == 5
        assert btc_profits2[RLS].position_profit == 3

        for profit1, profit2 in zip(btc_profits1.values(), btc_profits2.values()):
            assert profit1.id == profit2.id

    def test_pools_profit_position_sides(self):
        Position.objects.create(
            user_id=201,
            src_currency=BTC,
            dst_currency=USDT,
            side=Position.SIDES.buy,
            collateral=71,
            leverage=3,
            earned_amount=6,
            pnl=5,
            closed_at=self.base_date - timedelta(days=1),
        )
        Position.objects.create(
            user_id=202,
            src_currency=ETH,
            dst_currency=USDT,
            side=Position.SIDES.buy,
            collateral=92,
            leverage=4,
            earned_amount=5,
            pnl=2,
            closed_at=self.base_date - timedelta(days=2),
        )
        Position.objects.create(
            user_id=203,
            src_currency=USDT,
            dst_currency=RLS,
            side=Position.SIDES.sell,
            collateral=106,
            leverage=2,
            earned_amount=3,
            pnl=1,
            closed_at=self.base_date - timedelta(days=29),
        )
        self.usdt_pool.src_wallet.create_transaction(tp='buy', amount=6).commit()

        to_date = ir_today()
        from_date, _ = get_first_and_last_of_jalali_month(ir_today() - timedelta(days=1))
        pools_profits = PoolProfit.calc_pools_profit([self.usdt_pool], from_date, to_date)
        assert set(pools_profits.keys()) == {self.usdt_pool.id}
        usdt_profits = pools_profits[self.usdt_pool.id]
        assert set(usdt_profits.keys()) == {USDT, RLS}
        assert usdt_profits[USDT].position_profit == 4
        assert usdt_profits[RLS].position_profit == 2

    @override_settings(POOL_MAX_PROFIT_REPARATION_RATE=Decimal('0.2'))
    def test_pools_profit_on_notable_loss(self):
        to_date = ir_today()
        from_date, _ = get_first_and_last_of_jalali_month(ir_today() - timedelta(days=1))

        Position.objects.create(
            user=self.user1,
            src_currency=BTC,
            dst_currency=USDT,
            side=Position.SIDES.sell,
            collateral=213,
            earned_amount=20,
            pnl=14,
            closed_at=self.base_date - timedelta(days=1),
        )
        Position.objects.create(
            user_id=202,
            src_currency=BTC,
            dst_currency=USDT,
            side=Position.SIDES.sell,
            collateral=213,
            earned_amount=-216,
            pnl=-213,
            closed_at=self.base_date - timedelta(days=3),
        )

        pools_profit = PoolProfit.calc_pools_profit([self.btc_pool], from_date, to_date)
        btc_profits = pools_profit[self.btc_pool.id]
        assert btc_profits[USDT].position_profit == 8
        assert btc_profits[RLS].position_profit == 3

    def test_pools_profit_for_pool_without_rial_profit(self):
        self.ltc_pool = LiquidityPool.objects.create(
            currency=LTC,
            capacity=2,
            manager_id=412,
            is_active=True,
            activated_at=ir_now(),
        )
        Position.objects.create(
            user=self.user1,
            src_currency=LTC,
            dst_currency=USDT,
            side=Position.SIDES.sell,
            collateral=213,
            earned_amount=5,
            pnl=2,
            closed_at=self.base_date - timedelta(days=1),
        )
        to_date = ir_today()
        from_date, _ = get_first_and_last_of_jalali_month(ir_today() - timedelta(days=1))
        pools_profit = PoolProfit.calc_pools_profit([self.ltc_pool], from_date, to_date)
        assert len(pools_profit) == 1
        ltc_profits = pools_profit[self.ltc_pool.id]
        assert len(ltc_profits) == 2
        assert set(ltc_profits.keys()) == {RLS, USDT}
        assert ltc_profits[RLS].position_profit == Decimal('0')

    def test_populate_daily_pool_profit_convert_to_rial(self):
        with patch(
            'exchange.pool.models.LiquidityPool.profit_date',
            new_callable=PropertyMock,
            return_value=jdatetime.date(year=1400, month=12, day=1),
        ):
            from_date, to_date = get_first_and_last_of_jalali_month(ir_today() - timedelta(days=1))
            populate_daily_profit_for_target_pools(from_date, to_date + timedelta(days=1), LiquidityPool.objects.all())

        usdt_profits1 = PoolProfit.objects.get(pool=self.btc_pool, currency=USDT)
        assert usdt_profits1.position_profit == 4
        assert usdt_profits1.orders.count() == 1
        assert usdt_profits1.orders.first().amount == 4

    def test_populate_daily_pool_profit_reset(self):
        with patch(
            'exchange.pool.models.LiquidityPool.profit_date',
            new_callable=PropertyMock,
            return_value=jdatetime.date(year=1400, month=12, day=1),
        ):
            from_date, to_date = get_first_and_last_of_jalali_month(ir_today() - timedelta(days=1))
            populate_daily_profit_for_target_pools(from_date, to_date + timedelta(days=1), LiquidityPool.objects.all())

        self.shib_pool.refresh_from_db()
        assert self.shib_pool.current_profit == 0

    def test_pools_profit_cron(self):
        CalculateDailyPoolProfitsCron().run()

        from_date, to_date = get_first_and_last_of_jalali_month(ir_today() - timedelta(days=1))

        btc_pool_usdt_profit = PoolProfit.objects.filter(
            pool=self.btc_pool,
            currency=USDT,
        ).first()

        assert btc_pool_usdt_profit is not None
        assert btc_pool_usdt_profit.position_profit == 4
        assert btc_pool_usdt_profit.rial_value == 8000
        assert btc_pool_usdt_profit.to_date == to_date
        assert btc_pool_usdt_profit.from_date == from_date

        btc_pool_rls_profit = PoolProfit.objects.filter(
            pool=self.btc_pool,
            currency=RLS,
        ).first()

        assert btc_pool_rls_profit is not None
        assert btc_pool_rls_profit.position_profit == 3
        assert btc_pool_rls_profit.rial_value == 3
        assert btc_pool_rls_profit.to_date == to_date
        assert btc_pool_rls_profit.from_date == from_date

        Position.objects.create(
            user=self.user1,
            src_currency=BTC,
            dst_currency=USDT,
            side=Position.SIDES.sell,
            collateral=213,
            earned_amount=2,
            pnl=1,
            closed_at=self.base_date - timedelta(days=1),
        )

        CalculateDailyPoolProfitsCron().run()
        btc_pool_rls_profit2 = PoolProfit.objects.filter(
            pool=self.btc_pool,
            currency=USDT,
        ).first()

        assert btc_pool_rls_profit2 is not None
        assert btc_pool_rls_profit2.position_profit == 5

    def test_populate_realized_pool_profits(self):
        with patch(
            'exchange.pool.models.LiquidityPool.profit_date',
            new_callable=PropertyMock,
            return_value=jdatetime.date(year=1400, month=12, day=1),
        ):
            from_date, to_date = get_first_and_last_of_jalali_month(ir_today() - timedelta(days=1))
            populate_daily_profit_for_target_pools(from_date, to_date + timedelta(days=1), LiquidityPool.objects.all())

        usdt_profit = PoolProfit.objects.get(pool=self.btc_pool, currency=USDT)
        assert usdt_profit.orders.count() == 1

        with pytest.raises(PartialConversionOrderException):
            populate_realized_profits_for_target_pools(self.base_date - timedelta(days=30), LiquidityPool.objects.all())

        order = usdt_profit.orders.first()
        assert order
        order.status = Order.STATUS.done
        order.matched_total_price = 3000
        order.matched_amount = 4
        order.save()
        assert usdt_profit.orders .count() == 1

        populate_realized_profits_for_target_pools(self.base_date - timedelta(days=30), LiquidityPool.objects.all())
        self.btc_pool.refresh_from_db()
        assert self.btc_pool.current_profit == 3003

    @patch('exchange.pool.functions.create_or_update_pool_stat')
    @patch('exchange.pool.functions.populate_apr_of_target_pools')
    @patch('exchange.pool.functions.populate_realized_profits_for_target_pools')
    @patch('exchange.pool.functions.populate_users_delegation_score_on_target_pools')
    @patch('exchange.pool.functions.populate_users_profit_on_target_pools')
    @patch('exchange.pool.functions.distribute_user_profit_on_target_pools')
    @patch('exchange.pool.functions.convert_target_pools_usdt_profits_to_rial')
    def test_distribute_pool_current_profit_reset(self, *args):
        profit_wallet = Wallet.get_user_wallet(LiquidityPool.get_profit_collector(), USDT)
        profit_wallet.create_transaction(tp='pnl', amount=298).commit()
        with patch(
            'exchange.pool.models.LiquidityPool.profit_date',
            new_callable=PropertyMock,
            return_value=jdatetime.date(year=1400, month=12, day=1),
        ):
            from_date, to_date = get_first_and_last_of_jalali_month(self.base_date - timedelta(days=1))
            distribute_profits_for_target_pools(from_date, to_date, LiquidityPool.objects.all())

        self.shib_pool.refresh_from_db()
        assert self.shib_pool.current_profit == 0

        self.btc_pool.refresh_from_db()
        assert self.btc_pool.current_profit == 596000 # last position, (300 - 2) * price
        usdt_profits = PoolProfit.objects.filter(pool=self.btc_pool, currency=USDT)
        assert usdt_profits.count() == 2
