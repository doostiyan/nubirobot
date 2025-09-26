from decimal import Decimal
from typing import Union

from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User, VerificationProfile
from exchange.base.calendar import ir_now
from exchange.base.models import AMOUNT_PRECISIONS, Currencies, Settings, get_market_symbol
from exchange.base.money import quantize_number
from exchange.margin.models import Position
from exchange.market.models import Market, Order
from exchange.pool.models import LiquidityPool, PoolAccess
from exchange.wallet.estimator import PriceEstimator


class LiquidityPoolModelTest(TestCase):
    pool: LiquidityPool
    system_user: User

    @classmethod
    def setUpTestData(cls):
        cls.pool = LiquidityPool.objects.create(
            currency=Currencies.btc, capacity=2, manager_id=410, is_active=True, activated_at=ir_now()
        )
        cls.pool.src_wallet.create_transaction('manual', 1).commit()
        cls.pool.src_wallet.refresh_from_db()

    def test_available_balance(self):
        defaults = {
            'user_id': 201,
            'trade_type': Order.TRADE_TYPES.margin,
            'src_currency': Currencies.btc,
            'dst_currency': Currencies.usdt,
            'order_type': Order.ORDER_TYPES.sell,
            'amount': '0.01',
            'price': 21000,
            'status': Order.STATUS.active,
        }
        for data in (
            {},
            {'user_id': 202},
            {'trade_type': Order.TRADE_TYPES.spot},  # no effect
            {'dst_currency': Currencies.rls, 'price': 680_000_000_0},
            {'order_type': Order.ORDER_TYPES.buy},  # no effect
            {'matched_amount': '0.005'},
            {'status': Order.STATUS.canceled},  # no effect
            {'status': Order.STATUS.done, 'matched_amount': '0.001'},  # no effect
            {'side': Order.ORDER_TYPES.buy},  # no effect on 1st, but on 2nd
            {'order_type': Order.ORDER_TYPES.buy, 'side': Order.ORDER_TYPES.buy},  # no effect on 1st, but on 2nd
        ):
            side = data.pop('side', Order.ORDER_TYPES.sell)
            data = {**defaults, **data}
            order = Order.objects.create(**data)
            Position.objects.create(
                user_id=data['user_id'],
                src_currency=data['src_currency'],
                dst_currency=data['dst_currency'],
                side=side,
                collateral=Decimal(data['price']) * Decimal(data['amount']),
                earned_amount=1,
            ).orders.add(order, through_defaults={})
        # A sell side pool
        assert self.pool.available_balance == Decimal('0.965')

        # A buy side pool
        usdt_pool = LiquidityPool.objects.create(
            currency=Currencies.usdt, capacity=10000, manager_id=413, is_active=True, activated_at=ir_now()
        )
        Position.objects.filter(side=Position.SIDES.buy, collateral=21).update(earned_amount=1)
        usdt_pool.src_wallet.create_transaction('manual', usdt_pool.capacity).commit()
        assert usdt_pool.available_balance == 9788

    def test_user_delegation_limit(self):
        user = User.objects.get(pk=201)
        self.pool.filled_capacity = Decimal('1.4')
        for user_type, expected_limit in (
            (User.USER_TYPES.level0, 0),
            (User.USER_TYPES.level1, Decimal('0.042')),
            (User.USER_TYPES.trader, Decimal('0.21')),
            (User.USER_TYPES.level2, Decimal('0.21')),
            (User.USER_TYPES.verified, Decimal('0.42')),
            (User.USER_TYPES.trusted, Decimal('0.7')),
        ):
            user.user_type = user_type
            assert self.pool.get_user_delegation_limit(user) == expected_limit

    def test_min_delegation(self):
        self.pool.capacity = 100
        self.pool.save()
        symbol = get_market_symbol(self.pool.currency, Currencies.rls)
        cache.set(f'orderbook_{symbol}_best_active_buy', Decimal(100_0))

        Settings.set(LiquidityPool.MIN_DELEGATION_SETTING_KEY, 1_000_0)
        assert self.pool.min_delegation == Decimal('10')

        self.pool.capacity = 1
        self.pool.save()
        assert self.pool.min_delegation == Decimal('10')

        PriceEstimator.get_price_range.clear()
        cache.set(f'orderbook_{symbol}_best_active_buy', Decimal(3_000_0))
        assert self.pool.min_delegation == quantize_number(
            Decimal(1) / Decimal(3), AMOUNT_PRECISIONS[symbol])

        PriceEstimator.get_price_range.clear()
        cache.delete(f'orderbook_{symbol}_best_active_buy')
        assert self.pool.min_delegation == Decimal('0.01')  # 1% of capacity

    def test_max_delegation(self):
        user_type = User.USER_TYPES.level2  # Level2 User
        symbol = get_market_symbol(self.pool.currency, Currencies.rls)

        cache.set(f'orderbook_{symbol}_best_active_buy', Decimal(100_0))
        Settings.set(LiquidityPool.MAX_DELEGATION_SETTING_KEY % user_type, 100_0)
        assert self.pool.get_max_delegation(user_type) == Decimal('1')

        PriceEstimator.get_price_range.clear()
        cache.set(f'orderbook_{symbol}_best_active_buy', Decimal(300_0))
        assert self.pool.get_max_delegation(user_type) == quantize_number(
            Decimal(1) / Decimal(3),
            AMOUNT_PRECISIONS[symbol],
        )

        # When setting is not set, should fallback to lower type
        assert self.pool.get_max_delegation(User.USER_TYPES.trusted) == quantize_number(
            Decimal(1) / Decimal(3),
            AMOUNT_PRECISIONS[symbol],
        )

        # Testing fallback value for a user when no fallback exists
        assert self.pool.get_max_delegation(User.USER_TYPES.level1) == Decimal(0)

        # Testing fallback value for ineligible user for delegating
        assert self.pool.get_max_delegation(User.USER_TYPES.level0) == Decimal(0)

        PriceEstimator.get_price_range.clear()
        cache.delete(f'orderbook_{symbol}_best_active_buy')
        assert self.pool.min_delegation == Decimal('0.02')  # 1% of capacity

    def test_get_pools(self):
        user = User.objects.get(pk=201)
        PoolAccess.objects.create(
            access_type=PoolAccess.ACCESS_TYPES.liquidity_provider,
            user_type=user.user_type,
            liquidity_pool=self.pool,
        )
        PoolAccess.objects.create(
            access_type=PoolAccess.ACCESS_TYPES.liquidity_provider,
            user=user,
            liquidity_pool=self.pool,
        )

        pools = LiquidityPool.get_pools(
            access_type=PoolAccess.ACCESS_TYPES.liquidity_provider, user=user, is_active=True
        )
        assert pools.filter(id=self.pool.id).count() == 1


class LiquidityPoolAPITest(APITestCase):
    user: User
    system_user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        User.objects.filter(pk__in=(202, 203, 204)).update(user_type=User.USER_TYPES.system)
        cls.pools = [
            LiquidityPool(
                currency=Currencies.btc,
                capacity=10,
                filled_capacity=8,
                manager_id=202,
                is_active=True,
                apr=Decimal('1.23'),
                activated_at=ir_now(),
            ),
            LiquidityPool(
                currency=Currencies.ltc,
                capacity=30,
                filled_capacity=17,
                manager_id=203,
                is_active=False,
                activated_at=ir_now(),
            ),
            LiquidityPool(
                currency=Currencies.usdt,
                capacity=1000,
                filled_capacity=980,
                manager_id=204,
                is_active=True,
                activated_at=ir_now(),
            ),
            LiquidityPool(
                currency=Currencies.rls,
                capacity=100000000,
                filled_capacity=10000,
                manager_id=402,
                is_active=True,
                activated_at=ir_now(),
            ),
            LiquidityPool(
                currency=Currencies.eth,
                capacity=1000,
                filled_capacity=980,
                manager_id=412,
                is_active=False,
            ),
        ]
        LiquidityPool.objects.bulk_create(cls.pools)
        cls.private_user = User.objects.get(pk=202)
        cls.private_pools = [
            LiquidityPool.objects.create(
                currency=Currencies.xrp,
                capacity=100,
                filled_capacity=8,
                manager_id=400,
                is_active=True,
                is_private=True,
                current_profit=1,
                activated_at=ir_now(),
            ),
            LiquidityPool.objects.create(
                currency=Currencies.bch,
                capacity=200,
                filled_capacity=8,
                manager_id=410,
                is_active=True,
                is_private=True,
                current_profit=1,
                activated_at=ir_now(),
            ),
            LiquidityPool.objects.create(
                currency=Currencies.bnb,
                capacity=300,
                filled_capacity=8,
                manager_id=411,
                is_active=True,
                is_private=True,
                activated_at=ir_now(),
            ),
            LiquidityPool.objects.create(
                currency=Currencies.s,
                capacity=400,
                filled_capacity=400,
                manager_id=413,
                is_active=True,
                is_private=True,
                activated_at=ir_now(),
            ),
        ]
        cls.pool_accesses = [
            PoolAccess(
                access_type=PoolAccess.ACCESS_TYPES.liquidity_provider,
                user_type=cls.private_user.user_type,
                liquidity_pool=cls.private_pools[0],
            ),
            PoolAccess(
                access_type=PoolAccess.ACCESS_TYPES.liquidity_provider,
                user=cls.private_user,
                liquidity_pool=cls.private_pools[1],
            ),
            PoolAccess(
                access_type=PoolAccess.ACCESS_TYPES.liquidity_provider,
                user_type=User.USER_TYPES.normal,
                liquidity_pool=cls.private_pools[2],
            ),
            PoolAccess(
                access_type=PoolAccess.ACCESS_TYPES.liquidity_provider,
                user_type=cls.private_user.user_type,
                liquidity_pool=cls.private_pools[2],
                is_active=False,
            ),
            PoolAccess(
                access_type=PoolAccess.ACCESS_TYPES.trader,
                user_type=cls.private_user.user_type,
                liquidity_pool=cls.private_pools[2],
            ),
            PoolAccess(
                access_type=PoolAccess.ACCESS_TYPES.liquidity_provider,
                user_type=cls.private_user.user_type,
                liquidity_pool=cls.private_pools[3],
            ),
            PoolAccess(
                access_type=PoolAccess.ACCESS_TYPES.liquidity_provider,
                user=cls.private_user,
                liquidity_pool=cls.private_pools[3],
            ),
        ]
        PoolAccess.objects.bulk_create(cls.pool_accesses)

        cls.markets = {}
        Settings.set(LiquidityPool.MIN_DELEGATION_SETTING_KEY, 1_000_0)
        for pool in cls.pools:
            if pool.currency != Currencies.rls:
                market = Market.get_for(pool.currency, Currencies.rls)
                cls.markets[pool.currency] = market
                cache.set(f'orderbook_{market.symbol}_best_active_buy', Decimal(3_000_0))

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def _test_successful_pool_list(self, result_indexes: tuple, _status=None):
        response = self.client.get('/liquidity-pools/list', {'status': _status} if _status else {})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert 'pools' in data
        assert len(data['pools']) == len(result_indexes)
        for index in result_indexes:
            pool = self.pools[index]
            currency_code = ('btc', 'ltc', 'usdt', 'rls')[index]
            assert currency_code in data['pools']
            pool_data = data['pools'][currency_code]
            assert Decimal(pool_data['capacity']) == pool.capacity
            assert Decimal(pool_data['filledCapacity']) == pool.filled_capacity
            assert Decimal(pool_data['currentProfit']) == pool.current_profit
            assert pool_data['APR'] == (str(pool.apr) if pool.apr else None)
            if pool.currency != Currencies.rls:
                assert Decimal(pool_data['minDelegation']) == quantize_number(
                    Decimal('0.3333333'),
                    AMOUNT_PRECISIONS[self.markets[pool.currency].symbol],
                )
            assert pool.get_max_delegation(self.user.user_type) == Decimal(pool_data['maxDelegation'])
            assert Decimal(pool_data['availableBalance']) == pool.unfilled_capacity

            assert pool.start_date.isoformat() == pool_data['startDate']
            assert pool.end_date.isoformat() == pool_data['endDate']
            assert pool.profit_period == pool_data['profitPeriod']
            assert pool.profit_date.isoformat() == pool_data['profitDate']

    def _test_unsuccessful_pool_list(self, http_code: int, code: str, _status=None):
        response = self.client.get('/liquidity-pools/list', {'status': _status})
        assert response.status_code == http_code
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == code

    def test_list_pools(self):
        self._test_successful_pool_list((0, 2, 3))

    def test_list_pools_filter_status(self):
        self._test_successful_pool_list((0, 1, 2, 3), 'all')
        self._test_successful_pool_list((0, 2, 3), 'active')
        self._test_successful_pool_list((1,), 'inactive')
        self._test_unsuccessful_pool_list(400, 'ParseError', 'invalid')

    def test_list_pools_available_balance(self):
        self.pools[0].src_wallet.create_transaction('manual', '8.3').commit()  # Above filled capacity
        self.pools[2].src_wallet.create_transaction('manual', '679').commit()
        self.pools[3].src_wallet.create_transaction('manual', '100').commit()
        Position.objects.bulk_create(
            [
                Position(src_currency=10, collateral=200, user_id=201, **data)
                for data in (
                    {'dst_currency': 13, 'side': 1, 'earned_amount': 10},
                    {'dst_currency': 13, 'side': 1, 'earned_amount': -20},
                    {'dst_currency': 13, 'side': 2, 'earned_amount': 30},
                    {'dst_currency': 13, 'side': 2, 'earned_amount': -20},
                    {'dst_currency': 2, 'side': 2, 'earned_amount': 10},
                )
            ]
        )
        self._test_successful_pool_list((0, 2, 3))

    def test_private_pools(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.private_user.auth_token.key}')
        response = self.client.get('/liquidity-pools/list')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert 'pools' in data
        assert len(data['pools']) == 6

    def test_public_pools(self):
        self.client.credentials(HTTP_AUTHORIZATION='')
        response = self.client.get('/liquidity-pools/list')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert 'pools' in data
        assert len(data['pools']) == 3

    def test__multiple_pool_access__creating_alert__should_be_ok(self):
        VerificationProfile.objects.filter(id=self.private_user.get_verification_profile().id).update(
            email_confirmed=True
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.private_user.auth_token.key}')
        response = self.client.post(f'/liquidity-pools/{self.private_pools[3].id}/unfilled-capacity-alert/create')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
