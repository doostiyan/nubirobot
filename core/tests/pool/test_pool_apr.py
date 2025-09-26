from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.utils.timezone import now

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings
from exchange.pool.functions import calculate_apr, populate_apr_of_target_pools
from exchange.pool.models import LiquidityPool, PoolProfit, UserDelegation, UserDelegationProfit

BTC = Currencies.btc


class PoolAPRTest(TestCase):
    def setUp(self):
        self.to_date = now().date()
        self.from_date = self.to_date - timedelta(days=30)

        self.user1 = User.objects.get(pk=201)
        self.pool = LiquidityPool.objects.create(currency=BTC, capacity=20, manager_id=410, activated_at=ir_now())
        self.pool_profit = PoolProfit.objects.create(
            pool=self.pool,
            currency=Currencies.rls,
            position_profit=5000,
            rial_value=5000,
            from_date=self.from_date,
            to_date=self.to_date,
        )
        self.user_delegation = UserDelegation.objects.create(
            pool=self.pool, user=self.user1, balance=Decimal(0), closed_at=None,
        )
        Settings.set('liquidity_pool_day_in_row_factor', '0.1')
        cache.set('orderbook_BTCIRT_best_active_buy', Decimal(20000))

    def test_calculate_pool_apr(self):
        # when previous apr is null
        apr = calculate_apr(self.pool, Decimal(5000), self.from_date, self.to_date)
        # base_amount = 1
        # base_score = 124 = 1 * effective_days(31)
        # share of pool for base = 0.0248 = base_score / (5000)
        # total profit = 5000
        # base amount in rial = 20000
        # apr = 7.44 = 0.0248 * 5000 / 20000 * 100 * 12
        self.assertAlmostEqual(apr, Decimal('7.44'))

    def test_calculate_pool_apr_with_non_positive_profit(self):
        self.pool_profit.rial_value = Decimal('-10')
        self.pool_profit.save()

        apr = calculate_apr(self.pool, Decimal(5000), self.from_date, self.to_date)
        assert apr == 0

        self.pool_profit.rial_value = Decimal('0')
        self.pool_profit.save()
        apr = calculate_apr(self.pool, Decimal(5000), self.from_date, self.to_date)
        assert apr == 0

    def test_calculate_pool_apr_with_no_user(self):
        apr = calculate_apr(self.pool, Decimal(0), self.from_date, self.to_date)
        assert apr == 300

    def test_populate_apr_all_pools(self):
        user2 = User.objects.get(pk=202)
        user3 = User.objects.get(pk=203)
        user_delegation2 = UserDelegation.objects.create(pool=self.pool, user=user2, balance=Decimal(0), closed_at=None)
        user_delegation3 = UserDelegation.objects.create(pool=self.pool, user=user3, balance=Decimal(0), closed_at=None)

        UserDelegationProfit.objects.bulk_create([
            UserDelegationProfit(
                user_delegation=self.user_delegation,
                delegation_score=1000,
                from_date=self.from_date,
                to_date=self.to_date,
            ),
            UserDelegationProfit(
                user_delegation=user_delegation2,
                delegation_score=4000,
                from_date=self.from_date,
                to_date=self.to_date,
            ),
            UserDelegationProfit(
                user_delegation=user_delegation3,
                delegation_score=15000,
                from_date=self.from_date - timedelta(days=2),
                to_date=self.to_date,
            ),
        ])
        populate_apr_of_target_pools(self.from_date, self.to_date, LiquidityPool.objects.all())
        self.pool.refresh_from_db()
        assert self.pool.apr == Decimal('7.44')

        self.pool.apr = 10
        self.pool.save()
        populate_apr_of_target_pools(self.from_date, self.to_date, LiquidityPool.objects.all())
        self.pool.refresh_from_db()
        assert self.pool.apr == (10 + Decimal('7.44')) / 2
