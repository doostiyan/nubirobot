import pytest
from django.conf import settings
from django.test import Client, TestCase, override_settings

from exchange.accounts.models import User
from exchange.base.api import is_internal_ip, is_nobitex_server_ip
from exchange.base.helpers import get_global_ratelimit_throttle_settings, throttle_ratelimit
from exchange.base.models import Settings


@pytest.mark.unit()
def test_is_internal_ip():
    assert not is_internal_ip('')
    assert is_internal_ip('37.27.13.213')
    assert not is_internal_ip('135.181.178.175')
    assert is_internal_ip('94.182.183.1')
    assert not is_internal_ip('94.182.188.1')
    assert is_internal_ip('95.216.20.243')
    assert not is_internal_ip('95.215.20.243')


@override_settings(NOBITEX_SERVER_IPS=['1.1.1.0/28', '2.2.2.2', ''])
def test_is_nobitex_server_ip():
    assert not is_nobitex_server_ip('')
    assert not is_nobitex_server_ip('37.27.13.213')
    assert not is_nobitex_server_ip('1.1.1.16')  # not in the network
    assert is_nobitex_server_ip('1.1.1.1')
    assert is_nobitex_server_ip('2.2.2.2')
    assert not is_nobitex_server_ip('2.2.2.1')
    assert not is_nobitex_server_ip('2')
    assert not is_nobitex_server_ip('abc.a.b.c')


@pytest.mark.unit()
def test_throttle_ratelimit():
    for invalid_throttle_rate in (None, '10%', 5, -1, []):
        assert throttle_ratelimit('200/10m', invalid_throttle_rate, None) == '200/10m'
    assert throttle_ratelimit('200/10m', 1, None) == '200/10m'
    assert throttle_ratelimit('200/10m', 0.5, None) == '100/10m'
    assert throttle_ratelimit('200/10m', 0.1, None) == '20/10m'
    assert throttle_ratelimit('200/10m', 0.333, None) == '66/10m'
    assert throttle_ratelimit('200/10m', 0, None) == '0/m'
    assert throttle_ratelimit('200/10m', 1.3333, None) == '266/10m'
    assert throttle_ratelimit('200/10m', 4, None) == '800/10m'


@override_settings(RATELIMIT_ENABLE=True)
class DecoratorRateLimitTest(TestCase):
    """
        check ratelimit decorator and middleware
    """

    fixtures = ('test_data',)

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client = Client()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.original_allowed_hosts = settings.ALLOWED_HOSTS
        settings.ALLOWED_HOSTS.append('api2.nobitex.ir')

    def tearDown(self):
        settings.ALLOWED_HOSTS = self.original_allowed_hosts

    def test_ratelimit_function_based(self):
        responses = [self.client.get('/users/plans/deactivate').json() for i in range(2)]
        assert any(
            'status' in response and response['status'] == 'failed' and response['code'] == 'TooManyRequests'
            for response in responses
        )

    def test_ratelimit_class_based(self):
        responses = [self.client.get('/users/markets/favorite').json() for i in range(7)]
        assert any(
            'status' in response and response['status'] == 'failed' and response['code'] == 'TooManyRequests'
            for response in responses
        )

    def test_ratelimit_throttle(self):
        Settings.set_cached_json(
            'throttle_endpoint_rate_limits',
            {
                'exchange.market.views.orders_cancel_old': {'norm': 0.04, 'vip': 0.07},
                'exchange.market.views.orders_update_status': {
                    'norm': 0.03,
                    'ex_bot': 0.02,
                    'in_bot': 0.06,
                    'vip': 0.04,
                },
                'exchange.market.views.orders_list': {'norm': 0, 'in_bot': 0},
                'exchange.market.views.trades_list': {'norm': 0.07, 'in_bot': 0.15, 'vip': 0.01},
            },
        )
        # Test cancel-old: normal use throttled
        url_1 = '/market/orders/cancel-old'
        normal_user_responses = [self.client.post(url_1).json().get('code') for _ in range(2)]
        assert 'TooManyRequests' in normal_user_responses
        external_bot_response = self.client.post(url_1, HTTP_USER_AGENT='TraderBot/x').json()
        assert external_bot_response.get('code') is None
        internal_bot_response = self.client.post(url_1, REMOTE_ADDR='94.182.183.2').json()
        assert internal_bot_response['status'] == 'ok'
        vip_user_responses = [self.client.post(url_1, HTTP_HOST='api2.nobitex.ir').json().get('code') for _ in range(3)]
        assert 'TooManyRequests' in vip_user_responses
        assert None in vip_user_responses

        # Test update-status: all users throttled
        url_2 = '/market/orders/update-status'
        data = {'status': 'canceled', 'order': 4}
        external_bot_responses = [
            self.client.post(url_2, data, HTTP_USER_AGENT='TraderBot/x').json().get('code') for _ in range(2)
        ]
        assert None in external_bot_responses
        assert 'TooManyRequests' in external_bot_responses
        normal_user_responses = [self.client.post(url_2, data).json().get('code') for _ in range(3)]
        assert None in normal_user_responses
        assert 'TooManyRequests' in normal_user_responses
        internal_bot_response = self.client.post(url_2, data, REMOTE_ADDR='94.182.183.2').json()
        assert internal_bot_response.get('code') is None
        vip_user_responses = [
            self.client.post(url_2, data, HTTP_HOST='api2.nobitex.ir').json().get('code') for _ in range(4)
        ]
        assert vip_user_responses[-2] is None
        assert vip_user_responses[-1] == 'TooManyRequests'

        # Test order list: all users closed
        url_3 = '/market/orders/list'
        normal_user_response = self.client.get(url_3).json()
        assert normal_user_response.get('code') == 'TooManyRequests'
        external_bot_response = self.client.get(url_3, HTTP_USER_AGENT='TraderBot/x').json()
        assert external_bot_response.get('code') is None
        internal_bot_response = self.client.get(url_3, REMOTE_ADDR='94.182.183.2').json()
        assert internal_bot_response.get('code') == 'TooManyRequests'
        vip_user_response = self.client.get(url_3, HTTP_HOST='api2.nobitex.ir').json()
        assert vip_user_response.get('code') is None

        get_global_ratelimit_throttle_settings.clear()
        Settings.set_cached_json('global_throttle_rate_limits', {'norm': 1.5, 'ex_bot': 0, 'in_bot': 0.5, 'vip': 0})
        url = '/market/trades/list'
        normal_user_responses = [
            self.client.post(url, CONTENT_TYPE='application/json').json().get('code') for _ in range(4)
        ]
        assert 'TooManyRequests' in normal_user_responses
        assert None in normal_user_responses
        external_bot_response = self.client.post(url, HTTP_USER_AGENT='TraderBot/x').json()
        assert external_bot_response.get('code') == 'TooManyRequests'
        internal_bot_responses = [
            self.client.post(url, REMOTE_ADDR='37.27.13.213').json().get('code') for _ in range(2)
        ]
        assert 'TooManyRequests' not in internal_bot_responses
        internal_bot_response = self.client.post(url, REMOTE_ADDR='37.27.13.213').json()
        assert internal_bot_response.get('code') == 'TooManyRequests'
        vip_user_responses = self.client.post(url, HTTP_HOST='api2.nobitex.ir').json()
        assert vip_user_responses.get('code') == 'TooManyRequests'
