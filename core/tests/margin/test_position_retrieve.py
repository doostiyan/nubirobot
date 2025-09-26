from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.base.models import Currencies
from exchange.margin.models import Position
from tests.market.test_order import OrderTestMixin


class PositionRetrieveBaseAPITest(OrderTestMixin, APITestCase):
    MARKET_SYMBOL = 'BTCUSDT'
    MARKET_PRICE = 21220

    positions: list

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        now = timezone.now()
        defaults = {
            'user_id': cls.user.id,
            'src_currency': Currencies.btc,
            'dst_currency': Currencies.usdt,
            'side': Position.SIDES.sell,
            'delegated_amount': '0.09985',
            'collateral': '2500',
            'earned_amount': '2130',
            'liquidation_price': '46300',
            'status': Position.STATUS.open,
            'entry_price': '21300',
            'created_at': now - timezone.timedelta(days=1),
            'opened_at': now - timezone.timedelta(hours=10),
        }
        cls.positions = []
        for data in (
            {},
            {'user_id': 202},
            {'src_currency': Currencies.ltc},
            {
                'src_currency': Currencies.bnb,
                'status': Position.STATUS.new,
                'delegated_amount': 0,
                'earned_amount': 0,
                'entry_price': None,
                'opened_at': None,
            },
            {'dst_currency': Currencies.rls},
            {
                'earned_amount': '30.5',
                'status': Position.STATUS.closed,
                'pnl': '25.01',
                'exit_price': '19600',
                'closed_at': now,
            },
            {
                'earned_amount': '-2400',
                'status': Position.STATUS.liquidated,
                'pnl': '-2400',
                'exit_price': '46500',
                'closed_at': now,
            },
            {
                'delegated_amount': 0,
                'earned_amount': 0,
                'status': Position.STATUS.canceled,
                'pnl': 0,
                'entry_price': None,
                'opened_at': None,
            },
            {'earned_amount': 2, 'status': Position.STATUS.expired, 'pnl': 2, 'exit_price': '46500', 'closed_at': now},
            {'side': Position.SIDES.buy, 'leverage': '2', 'collateral': '1065', 'earned_amount': '-2130'},
            {'earned_amount': 0, 'status': Position.STATUS.expired, 'pnl': 0, 'entry_price': None, 'opened_at': None},
        ):
            cls.positions.append(Position.objects.create(**{**defaults, **data}))
        cache.set(f'mark_price_{Currencies.btc}', Decimal('42700'))
        cls.set_market_price(50_000_0, 'USDTIRT')

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')


class PositionListAPITest(PositionRetrieveBaseAPITest):

    def _test_successful_position_list(
        self, filter_data: dict, result_indexes: tuple, *, has_next: bool = False, **headers
    ):
        response = self.client.get('/positions/list', filter_data, **headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert 'positions' in data
        assert len(data['positions']) == len(result_indexes)
        for position_data, index in zip(data['positions'], result_indexes):
            assert position_data['createdAt'] == self.positions[index].created_at.isoformat()
            if index in (5, 6, 7, 8):
                assert 'marginRatio' not in position_data
            else:
                assert 'marginRatio' in position_data
                assert 'markPrice' in position_data
        assert data['hasNext'] == has_next

    def _test_unsuccessful_position_list(self, data: dict, code: str):
        response = self.client.get('/positions/list', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == code

    def test_position_list_status(self):
        self._test_successful_position_list({}, (9, 4, 2, 0))
        self._test_successful_position_list({'status': 'active'}, (9, 4, 2, 0))
        self._test_successful_position_list({'status': 'past'}, (8, 6, 5))
        self._test_successful_position_list({'status': 'all'}, (9, 8, 6, 5, 4, 2, 0))

    def test_position_list_markets(self):
        self._test_successful_position_list({'srcCurrency': 'btc'}, (9, 4, 0))
        self._test_successful_position_list({'dstCurrency': 'usdt'}, (9, 2, 0))
        self._test_successful_position_list(
            {'status': 'all', 'srcCurrency': 'btc', 'dstCurrency': 'usdt'}, (9, 8, 6, 5, 0)
        )

    def test_position_list_side(self):
        self._test_successful_position_list({'side': 'sell'}, (4, 2, 0))
        self._test_successful_position_list({'side': 'buy'}, (9,))

    def test_position_list_sell_only_on_old_app_versions(self):
        self._test_successful_position_list({}, (4, 2, 0), HTTP_USER_AGENT='Android/5.2.9')

    def test_position_list_pagination(self):
        self._test_successful_position_list({'status': 'all', 'pageSize': 4}, (9, 8, 6, 5), has_next=True)
        self._test_successful_position_list({'status': 'all', 'pageSize': 4, 'page': 2}, (4, 2, 0), has_next=False)
        self._test_successful_position_list({'status': 'all', 'pageSize': 4, 'page': 3}, (), has_next=False)

    def test_position_list_invalid_inputs(self):
        for _status in ('test', 5, 'liquidated'):
            self._test_unsuccessful_position_list({'status': _status}, 'ParseError')
        for currency in ('test', 5, 'Bitcoin'):
            self._test_unsuccessful_position_list({'srcCurrency': currency}, 'ParseError')
            self._test_unsuccessful_position_list({'dstCurrency': currency}, 'ParseError')


class PositionCountAPITest(PositionRetrieveBaseAPITest):
    def _test_successful_position_count(self, filter_data: dict, count: int, **headers):
        response = self.client.get('/positions/active-count', filter_data, **headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert data['count'] == count

    def _test_unsuccessful_position_count(self, data: dict, code: str):
        response = self.client.get('/positions/list', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == code

    def test_position_count(self):
        self._test_successful_position_count({}, 4)

    def test_position_count_sell_only_on_old_app_versions(self):
        self._test_successful_position_count({}, 3, HTTP_USER_AGENT='Android/5.2.9')

    def test_position_list_invalid_inputs(self):
        for status in ('test', 5, 'liquidated'):
            self._test_unsuccessful_position_count({'status': status}, 'ParseError')
        for currency in ('test', 5, 'Bitcoin'):
            self._test_unsuccessful_position_count({'srcCurrency': currency}, 'ParseError')
            self._test_unsuccessful_position_count({'dstCurrency': currency}, 'ParseError')


class PositionDetailAPITest(PositionRetrieveBaseAPITest):

    def _test_successful_position_status(self, position_id: int, expected_values: dict):
        response = self.client.get(f'/positions/{position_id}/status')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert 'position' in data
        for key, value in expected_values.items():
            assert data['position'][key] == value
        if data['position']['status'] == 'Open':
            assert 'marginRatio' in data['position']
        else:
            assert 'marginRatio' not in data['position']

    def _test_unsuccessful_position_status(self, position_id: int, code: str):
        response = self.client.get(f'/positions/{position_id}/status')
        if code == 'NotFound':
            assert response.status_code == status.HTTP_404_NOT_FOUND
            return
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == code

    def test_position_status_active_position(self):
        expected_values = {
            'side': 'sell',
            'srcCurrency': 'btc',
            'dstCurrency': 'usdt',
            'delegatedAmount': '0.09985',
            'liability': '0.099979974',
            'collateral': '2500',
            'totalAsset': '4630',
            'liquidationPrice': '46300',
            'status': 'Open',
            'marginRatio': None,
            'liabilityInOrder': '0',
            'assetInOrder': '0',
            'leverage': '1',
        }
        self._test_successful_position_status(
            self.positions[0].id, {**expected_values, 'marginRatio': '2.18', 'markPrice': '42700'}
        )
        self._test_successful_position_status(self.positions[2].id, {**expected_values, 'srcCurrency': 'ltc'})
        self._test_successful_position_status(
            self.positions[4].id,
            {
                **expected_values,
                'dstCurrency': 'rls',
                'liability': '0.1001002507',
                'markPrice': '21350000000',
            },
        )
        self._test_successful_position_status(
            self.positions[9].id,
            {
                **expected_values,
                'side': 'buy',
                'leverage': '2',
                'liability': '0.09985',
                'collateral': '1065',
                'totalAsset': '3183.817',
                'marginRatio': '1.49',
                'markPrice': '42700',
            },
        )

    def test_position_status_inactive_position(self):
        for i in (5, 6, 8):
            self._test_successful_position_status(self.positions[i].id, {'id': self.positions[i].id})
        self._test_unsuccessful_position_status(self.positions[7].id, code='NotFound')

    def test_position_status_wrong_id(self):
        self._test_unsuccessful_position_status(-1, code='NotFound')

    def test_position_status_for_other_user(self):
        self._test_unsuccessful_position_status(self.positions[1].id, code='NotFound')
