from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings
from exchange.market.models import MarketCandle
from exchange.pool.functions import create_or_update_pool_stat, effective_days
from exchange.pool.models import LiquidityPool, PoolProfit, UserDelegation, UserDelegationProfit, PoolStat


class PoolStatTest(TestCase):
    def setUp(self):
        self.to_datetime = ir_now()
        self.to_date = self.to_datetime.date()
        self.from_date = self.to_date - timedelta(days=29)

        Settings.set('liquidity_pool_day_in_row_factor', '0.1')
        cache.set('orderbook_BTCIRT_best_active_buy', 20000)

        self.user1 = User.objects.get(pk=201)
        user2 = User.objects.get(pk=202)
        user3 = User.objects.get(pk=203)
        self.btc_pool = LiquidityPool.objects.create(currency=Currencies.btc, capacity=20, manager_id=410, filled_capacity=5, activated_at=ir_now())
        self.shib_pool = LiquidityPool.objects.create(currency=Currencies.shib, capacity=30, manager_id=412, activated_at=ir_now())
        eth_pool = LiquidityPool.objects.create(currency=Currencies.eth, capacity=30, manager_id=411, activated_at=ir_now())

        self.user_delegation = UserDelegation.objects.create(pool=self.btc_pool, user=self.user1, balance=Decimal(0), closed_at=None)
        user_delegation1 = UserDelegation.objects.create(pool=self.btc_pool, user=user2, balance=Decimal(0), closed_at=None)
        user_delegation2 = UserDelegation.objects.create(pool=eth_pool, user=user3, balance=Decimal(0), closed_at=None)
        user_delegation3 = UserDelegation.objects.create(pool=self.btc_pool, user=user3, balance=Decimal(0), closed_at=None)

        UserDelegationProfit.objects.bulk_create([
            UserDelegationProfit(
                user_delegation=self.user_delegation,
                delegation_score=1000,
                from_date=self.from_date,
                to_date=self.to_date,
            ),
            UserDelegationProfit(
                user_delegation=self.user_delegation,
                delegation_score=4000,
                from_date=self.from_date - timedelta(days=30),
                to_date=self.to_date - timedelta(days=30),
            ),
            UserDelegationProfit(
                user_delegation=user_delegation1,
                delegation_score=15000,
                from_date=self.from_date,
                to_date=self.to_date,
            ),
            UserDelegationProfit(
                user_delegation=user_delegation3,
                delegation_score=15000,
                from_date=self.from_date - timedelta(days=1),
                to_date=self.to_date,
            ),
            UserDelegationProfit(
                user_delegation=user_delegation2,
                delegation_score=15000,
                from_date=self.from_date,
                to_date=self.to_date,
            ),
        ])

        MarketCandle.objects.bulk_create([
            MarketCandle(
                market=self.btc_pool.get_market(Currencies.rls),
                start_time=self.to_datetime,
                resolution=MarketCandle.RESOLUTIONS.day,
                open_price=24, close_price=20000, low_price=26, high_price=27,
            ),
            MarketCandle(
                market=self.btc_pool.get_market(Currencies.usdt),
                start_time=self.to_datetime,
                resolution=MarketCandle.RESOLUTIONS.day,
                open_price=9, close_price=10, low_price=11, high_price=12,
            ),
            MarketCandle(
                market=self.btc_pool.get_market(Currencies.rls),
                start_time=self.to_datetime + timedelta(hours=25),
                resolution=MarketCandle.RESOLUTIONS.day,
                open_price=3, close_price=5, low_price=6, high_price=7,
            )
        ])

        PoolProfit.objects.bulk_create([
            PoolProfit(
                pool=self.btc_pool,
                from_date=self.from_date,
                to_date=self.to_date,
                currency=Currencies.rls,
                position_profit=900,
                rial_value=9000,
            ),
            PoolProfit(
                pool=self.btc_pool,
                from_date=self.from_date,
                to_date=self.to_date,
                currency=Currencies.usdt,
                position_profit=4,
                rial_value=1000,
            ),
            PoolProfit(
                pool=self.btc_pool,
                from_date=self.from_date + timedelta(days=1),
                to_date=self.to_date,
                currency=Currencies.rls,
                position_profit=1000,
                rial_value=5000,
            ),
            PoolProfit(
                pool=self.shib_pool,
                from_date=self.from_date,
                to_date=self.to_date,
                currency=Currencies.usdt,
                position_profit=4,
                rial_value=2000,
            ),
        ])

    def test_pool_stat(self):
        btc_pool_stat = create_or_update_pool_stat(self.btc_pool, self.from_date, self.to_date, self.to_date)

        btc_pool_stat_in_db = PoolStat.objects.filter(pk=btc_pool_stat.pk)
        assert btc_pool_stat is not None
        assert btc_pool_stat_in_db.count() == 1
        assert btc_pool_stat_in_db.first() == btc_pool_stat
        assert btc_pool_stat.pk is not None
        assert btc_pool_stat.pool == self.btc_pool
        assert btc_pool_stat.from_date == self.from_date
        assert btc_pool_stat.to_date == self.to_date
        assert btc_pool_stat.total_delegators == 2
        assert btc_pool_stat.capacity == 20
        assert btc_pool_stat.balance == 5
        assert btc_pool_stat.avg_balance == Decimal(16000) / effective_days(self.btc_pool.profit_period)
        assert btc_pool_stat.apr == Decimal('4.3875') # 10000 (profit) / 16000 (total score) * 117 (base score) / 20000 * 12 * 100
        assert btc_pool_stat.token_price == 20000
        assert btc_pool_stat.total_profit_in_rial == 10000

    def test_pool_stat_when_no_record_exists(self):
        shib_pool_stat = create_or_update_pool_stat(self.shib_pool, self.from_date, self.to_date, self.to_date)
        assert shib_pool_stat.total_delegators == 0
        assert shib_pool_stat.capacity == 30
        assert shib_pool_stat.balance == 0
        assert shib_pool_stat.avg_balance == 0
        assert shib_pool_stat.apr == 0

    def test_pool_stat_call_more_than_once(self):
        btc_pool_stat1 = create_or_update_pool_stat(self.btc_pool, self.from_date, self.to_date, self.to_date)
        btc_pool_stat2 = create_or_update_pool_stat(self.btc_pool, self.from_date, self.to_date, self.to_date)

        btc_pool_stat_in_db = PoolStat.objects.filter(pk=btc_pool_stat1.pk)
        assert btc_pool_stat1 is not None
        assert btc_pool_stat_in_db.count() == 1
        assert btc_pool_stat_in_db.first() == btc_pool_stat1 == btc_pool_stat2
