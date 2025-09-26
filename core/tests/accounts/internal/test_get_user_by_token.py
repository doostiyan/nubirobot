import uuid
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from exchange.accounts.models import User


@override_settings(IS_INTERNAL_INSTANCE=True)
class TestGetUserByToken(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user.uid = uuid.UUID('1e7cdaa8-5cb1-4eea-9e98-e0725a07f8c4')
        self.user.save()

    def call(self, token: str) -> dict:
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {token}'
        return self.client.get('/internal/get-user')

    @patch('exchange.base.api_v2_1.is_nobitex_server_ip', Mock(return_value=False))
    def test_non_internal_ip(self):
        assert self.call('user201token').status_code == 404

    @patch('exchange.base.api_v2_1.is_nobitex_server_ip', Mock(return_value=True))
    def test_invalid_token(self):
        assert self.call('invalidToken').status_code == 401

    @patch('exchange.base.api_v2_1.is_nobitex_server_ip', Mock(return_value=True))
    def test_a_successful_call(self):
        response = self.call('user201token')
        assert response.status_code == 200
        headers = self.call('user201token').headers
        assert headers['User-ID'] == '1e7cdaa8-5cb1-4eea-9e98-e0725a07f8c4'
        assert headers['User-Level'] == 'level0'
