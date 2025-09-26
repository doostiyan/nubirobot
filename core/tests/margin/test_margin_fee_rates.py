from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings
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
            LiquidityPool.objects.create(
                currency=Currencies.ltc, capacity=10, manager_id=1000, is_active=False, activated_at=ir_now()
            ),
        ]
        PoolAccess.objects.create(
            access_type=PoolAccess.ACCESS_TYPES.trader,
            user_type=User.USER_TYPES.level0,
            liquidity_pool=cls.pools[1],
        )
        PoolAccess.objects.create(
            access_type=PoolAccess.ACCESS_TYPES.trader,
            user_type=User.USER_TYPES.trusted,
            liquidity_pool=cls.pools[2],
        )
        for pool in LiquidityPool.objects.all():
            Settings.set(f'{Settings.CACHEABLE_PREFIXES.position_fee_rate.value}_{pool.currency}', Decimal('0.001'))

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def _test_successful_fee_rates_list(self, expected_status_code: int, expected_data: dict = None):
        response = self.client.get('/margin/fee-rates')
        assert response.status_code == expected_status_code
        if expected_status_code == status.HTTP_200_OK:
            data = response.json()
            assert data['status'] == 'ok'
            assert 'feeRates' in data
            rates_dict = {item['currency']: item['positionFeeRate'] for item in data['feeRates']}
            assert rates_dict.keys() == expected_data.keys()
            for currency in rates_dict:
                fee_rate = expected_data.get(currency)
                assert rates_dict[currency] == fee_rate

    def test_margin_fee_rates_list_level0(self):
        self._test_successful_fee_rates_list(status.HTTP_200_OK, {'btc': '0.001', 'usdt': '0.001'})

    def test_margin_fee_rates_list_public(self):
        self.client.credentials(HTTP_AUTHORIZATION='')
        self._test_successful_fee_rates_list(status.HTTP_401_UNAUTHORIZED)
