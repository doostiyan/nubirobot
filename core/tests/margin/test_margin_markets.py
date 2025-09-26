from decimal import Decimal
from typing import Optional

from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings, parse_market_symbol
from exchange.pool.models import LiquidityPool, PoolAccess


class MarginMarketListAPITest(APITestCase):

    pools: list

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        cls.pools = [
            LiquidityPool.objects.create(
                currency=Currencies.btc,
                capacity=10,
                manager_id=410,
                is_active=True,
                activated_at=ir_now(),
            ),
            LiquidityPool.objects.create(
                currency=Currencies.usdt,
                capacity=1000,
                manager_id=413,
                is_active=True,
                is_private=True,
                activated_at=ir_now(),
            ),
            LiquidityPool.objects.create(currency=Currencies.ltc, capacity=10, manager_id=1000, is_active=False, activated_at=ir_now()),
        ]
        PoolAccess.objects.create(
            access_type=PoolAccess.ACCESS_TYPES.trader,
            user_type=User.USER_TYPES.trusted,
            liquidity_pool=cls.pools[1],
        )
        Settings.set(f'margin_max_leverage_{User.USER_TYPES.level2}', '3')
        Settings.set(f'margin_max_leverage_{User.USER_TYPES.verified}', '5')
        for pool in LiquidityPool.objects.all():
            Settings.set(f'position_fee_rate_{pool.currency}', Decimal('0.001'))

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def _test_successful_market_list(self, expected_markets: set, extra_data: Optional[dict] = None):
        response = self.client.get('/margin/markets/list')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert 'markets' in data
        assert set(data['markets']) == expected_markets
        extra_data = extra_data or {}
        for symbol in data['markets']:
            symbol_data = extra_data.get(symbol, {})
            assert data['markets'][symbol]['positionFeeRate'] == symbol_data.get('positionFeeRate', '0.001')
            assert data['markets'][symbol]['maxLeverage'] == symbol_data.get('maxLeverage', '1')
            assert data['markets'][symbol]['sellEnabled'] == symbol_data.get('sellEnabled', False)
            assert data['markets'][symbol]['buyEnabled'] == symbol_data.get('buyEnabled', False)
            assert parse_market_symbol(symbol) == (
                getattr(Currencies, data['markets'][symbol]['srcCurrency']),
                getattr(Currencies, data['markets'][symbol]['dstCurrency']),
            )

    def test_margin_market_list_level0(self):
        self._test_successful_market_list({'BTCIRT', 'BTCUSDT'}, {
            'BTCIRT': {'maxLeverage': '1', 'sellEnabled': True},
            'BTCUSDT': {'maxLeverage': '1', 'sellEnabled': True},
        })

    def test_margin_market_list_level_with_lower_max_leverage(self):
        User.objects.filter(pk=self.user.pk).update(user_type=User.USER_TYPES.level2)
        self._test_successful_market_list({'BTCIRT', 'BTCUSDT'}, {
            'BTCIRT': {'maxLeverage': '3', 'sellEnabled': True},
            'BTCUSDT': {'maxLeverage': '3', 'sellEnabled': True},
        })

    def test_margin_market_list_level4(self):
        User.objects.filter(pk=self.user.pk).update(user_type=User.USER_TYPES.trusted)
        self._test_successful_market_list(
            {'BTCIRT', 'BTCUSDT', 'USDTIRT', 'ETHUSDT', 'LTCUSDT'},
            {
                'BTCIRT': {'maxLeverage': '5', 'sellEnabled': True},
                'BTCUSDT': {'maxLeverage': '5', 'sellEnabled': True, 'buyEnabled': True},
                'USDTIRT': {'maxLeverage': '3', 'sellEnabled': True},
                # The corresponding view has to be fixed in a backward incompatible way in future
                'ETHUSDT': {'maxLeverage': '4', 'buyEnabled': True, 'positionFeeRate': '0'},
                'LTCUSDT': {'maxLeverage': '2', 'buyEnabled': True},
            },
        )

    def test_margin_market_list_public(self):
        self.client.credentials(HTTP_AUTHORIZATION='')
        self._test_successful_market_list(
            {'BTCIRT', 'BTCUSDT'},
            {
                'BTCIRT': {'maxLeverage': '5', 'sellEnabled': True},
                'BTCUSDT': {'maxLeverage': '5', 'sellEnabled': True},
            },
        )
