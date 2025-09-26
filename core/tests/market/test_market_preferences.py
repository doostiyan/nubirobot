import json

from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.market.models import UserMarketsPreferences


class TestFavoriteMarkets(APITestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def _call_api(self, favorite_market='', method='POST'):
        if method == 'POST':
            return self.client.post(
                path='/users/markets/favorite',
                data={'market': favorite_market},
            )
        elif method == 'GET':
            return self.client.get(path='/users/markets/favorite')
        else:
            return self.client.delete(path='/users/markets/favorite',
                                      data={'market': favorite_market})

    def test_set_favorite_markets_no_data(self):
        favorite_markets = json.loads(UserMarketsPreferences.get_favorite_markets(self.user))
        assert favorite_markets == []

        response = self._call_api()
        self.assertDictEqual(response.json(), {
            'status': 'failed',
            'code': 'InvalidData',
            'message': 'market is necessary',
        })
        assert response.status_code == 400

    def test_set_favorite_markets_parse_error(self):
        favorite_markets = json.loads(UserMarketsPreferences.get_favorite_markets(self.user))
        assert favorite_markets == []

        response = self._call_api('NOBIIRT')
        self.assertDictEqual(
            response.json(),
            {
                'status': 'failed',
                'code': 'InvalidData',
                'message': 'NOBIIRT is not a valid market!',
            },
        )
        assert response.status_code == 400

    def test_set_multiple_favorite_markets_parse_error(self):
        response = self._call_api('BTCUSDT,NOBIIRT')
        self.assertDictEqual(
            response.json(),
            {
                'status': 'failed',
                'code': 'InvalidData',
                'message': 'NOBIIRT is not a valid market!',
            },
        )
        assert response.status_code == 400

    def test_set_favorite_markets_success(self):
        favorite_markets = json.loads(UserMarketsPreferences.get_favorite_markets(self.user))
        assert favorite_markets == []

        response = self._call_api('BTCIRT')
        self.assertDictEqual(
            response.json(),
            {
                'status': 'ok',
                'favoriteMarkets': ['BTCIRT'],
            },
        )
        assert response.status_code == 200

    def test_set_multiple_favorite_markets_success(self):
        response = self._call_api('BTCIRT,     DOGEIRT, ETHIRT')
        self.assertDictEqual(
            response.json(),
            {
                'status': 'ok',
                'favoriteMarkets': ['BTCIRT', 'DOGEIRT', 'ETHIRT'],
            },
        )
        assert response.status_code == 200

    def test_get_favorite_markets(self):

        response = self._call_api(method='GET')
        self.assertDictEqual(response.json(), {
            'status': 'ok',
            'favoriteMarkets': [],
        })
        assert response.status_code == 200

        response = self._call_api('BTCIRT')
        self.assertDictEqual(
            response.json(),
            {
                'status': 'ok',
                'favoriteMarkets': ['BTCIRT'],
            },
        )
        assert response.status_code == 200

        response = self._call_api(method='GET')
        self.assertDictEqual(
            response.json(),
            {
                'status': 'ok',
                'favoriteMarkets': ['BTCIRT'],
            },
        )
        assert response.status_code == 200

    def test_delete_favorite_market_fail(self):
        _ = self._call_api('BTCIRT')
        response = self._call_api('BTCUSDT')
        self.assertDictEqual(
            response.json(),
            {
                'status': 'ok',
                'favoriteMarkets': ['BTCIRT', 'BTCUSDT'],
            },
        )
        assert response.status_code == 200
        user_fc = json.loads(UserMarketsPreferences.get_favorite_markets(self.user))
        assert user_fc == ['BTCIRT', 'BTCUSDT']

        response = self._call_api(method='DELETE')
        self.assertDictEqual(
            response.json(),
            {
                'status': 'failed',
                'code': 'InvalidData',
                'message': 'market is necessary (All or MarketSymbol)',
            },
        )
        user_fc = json.loads(UserMarketsPreferences.get_favorite_markets(self.user))
        assert user_fc == ['BTCIRT', 'BTCUSDT']

    def test_delete_favorite_market(self):
        _ = self._call_api('BTCIRT')
        response = self._call_api('BTCUSDT')
        self.assertDictEqual(
            response.json(),
            {
                'status': 'ok',
                'favoriteMarkets': ['BTCIRT', 'BTCUSDT'],
            },
        )
        assert response.status_code == 200
        user_fc = json.loads(UserMarketsPreferences.get_favorite_markets(self.user))
        assert user_fc == ['BTCIRT', 'BTCUSDT']

        response = self._call_api(method='DELETE', favorite_market='BTCIRT')
        self.assertDictEqual(
            response.json(),
            {
                'status': 'ok',
                'favoriteMarkets': ['BTCUSDT'],
            },
        )
        user_fc = json.loads(UserMarketsPreferences.get_favorite_markets(self.user))
        assert user_fc == ['BTCUSDT']

    def test_delete_all_favorite_market(self):
        _ = self._call_api('BTCIRT')
        response = self._call_api('BTCUSDT')
        self.assertDictEqual(
            response.json(),
            {
                'status': 'ok',
                'favoriteMarkets': ['BTCIRT', 'BTCUSDT'],
            },
        )
        assert response.status_code == 200
        user_fc = json.loads(UserMarketsPreferences.get_favorite_markets(self.user))
        assert user_fc == ['BTCIRT', 'BTCUSDT']

        response = self._call_api(method='DELETE', favorite_market='all')
        self.assertDictEqual(response.json(), {
            'status': 'ok',
            'favoriteMarkets': [],
        })
        user_fc = json.loads(UserMarketsPreferences.get_favorite_markets(self.user))
        assert user_fc == []


class TestFavoriteMarketsList(APITestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def _call_api(self):
        return self.client.get(path='/users/markets/favorite/list')

    def test_get_favorite_markets(self):

        response = self._call_api()
        assert response.json() == {
            'status': 'ok',
            'favoriteMarkets': [],
        }
        assert response.status_code == 200

        UserMarketsPreferences.set_favorite_market(self.user, 'BTCIRT')
        response = self._call_api()
        assert response.json() == {
            'status': 'ok',
            'favoriteMarkets': [
                'BTCIRT',
            ],
        }
        assert response.status_code == 200

        UserMarketsPreferences.set_favorite_market(self.user, 'ETHIRT')
        response = self._call_api()
        assert response.json() == {
            'status': 'ok',
            'favoriteMarkets': ['BTCIRT', 'ETHIRT'],
        }
        assert response.status_code == 200
