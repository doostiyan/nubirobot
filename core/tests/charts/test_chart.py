from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.charts.models import Chart


class ChartAPITest(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.patch = '/charts/storage/1.1/charts'
        cls.user: User = User.objects.get(pk=201)

    def setUp(self):
        self.chart1 = Chart.objects.create(
            user_id=self.user.id, ownerSource='nobitex', symbol='BTCIRT', lastModified='2024-06-12', name='test-name'
        )

    def _assert_successful_creation(self, response, expected_chart):
        assert response.status_code == 200

        r = response.json()
        assert r['status'] == 'ok'
        assert 'id' in r

        chart = Chart.objects.get(id=r['id'])
        assert chart.name == expected_chart['name']
        assert chart.id != self.chart1.id
        assert chart.symbol == expected_chart['symbol']
        assert chart.resolution == expected_chart['resolution']
        assert chart.content == expected_chart['content']
        assert chart.lastModified is not None

    def _assert_successful_update(self, response, body):

        assert response.status_code == 200

        r = response.json()
        assert r == {'status': 'ok'}
        last_modified = self.chart1.lastModified

        self.chart1.refresh_from_db()
        assert self.chart1.name == body['name']
        assert self.chart1.symbol == body['symbol']
        assert self.chart1.resolution == body['resolution']
        assert self.chart1.content == body['content']
        assert self.chart1.lastModified != last_modified


    def test_get_chart_without_token(self, *_):
        response = self.client.get(self.patch, {'client': 'nobitex', 'user': 'public', 'chart': self.chart1.id})
        assert response.status_code == 401

    def test_get_chart_by_authenticated_user(self, *_):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        response = self.client.get(self.patch, {'client': 'nobitex', 'chart': self.chart1.id})
        assert response.status_code == 200

        r = response.json()

        assert r['status'] == 'ok'
        assert r['data']['name'] == 'test-name'
        assert r['data']['id'] == self.chart1.id

    def test_get_chart_when_chart_does_not_exist(self, *_):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        response = self.client.get(self.patch, {'client': 'nobitex', 'chart': 12312})
        assert response.status_code == 200

        r = response.json()

        assert r['status'] == 'error'
        assert r['message'] == 'Chart not found'

    def test_delete_chart_using_authenticated_user(self, *_):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        response = self.client.delete(self.patch + f'?client=nobitex&chart={self.chart1.id}')
        assert response.status_code == 200

        r = response.json()
        assert r == {'status': 'ok'}

        assert Chart.objects.filter(id=self.chart1.id).first() is None



    def test_update_chart_using_authenticated_user(self, *_):
        body = {'name': 'amirReza', 'symbol': 'BTCIRT', 'resolution': '60', 'content': '{"key":"value"}'}

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        response = self.client.post(self.patch + f'?client=nobitex&chart={self.chart1.id}', data=body)

        self._assert_successful_update(response, body)

    def test_update_chart_by_user_id_with_wrong_token_format(self, *_):
        body = {'name': 'amirReza', 'symbol': 'BTCIRT', 'resolution': '60', 'content': '{"key":"value"}'}

        self.client.credentials(HTTP_AUTHORIZATION=f'{self.user.auth_token.key}')
        response = self.client.post(
            self.patch + f'?client=nobitex&chart={self.chart1.id}&user={self.user.id}', data=body
        )

        assert response.status_code == 401



    def test_create_chart_using_authenticated_user(self, *_):
        body = {'name': 'amirReza', 'symbol': 'BTCIRT', 'resolution': '60', 'content': '{"key":"value"}'}

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        response = self.client.post(self.patch + '?client=nobitex', data=body)

        self._assert_successful_creation(response, body)

    def test_create_chart_long_name(self, *_):
        name_max_length = Chart._meta.get_field('name').max_length
        chart_name = 'n' * (name_max_length + 1)
        body = {'name': chart_name, 'symbol': 'BTCIRT', 'resolution': '60', 'content': '{"key":"value"}'}

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        response = self.client.post(self.patch + '?client=nobitex', data=body)
        # Name of chart is greater than max length, so we expect that request fails with 400 status code.
        assert response.status_code == 400
        assert response.json().get('message')  # Error message must be passed to the client
