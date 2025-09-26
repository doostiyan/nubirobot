import pytest
import responses
from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import User
from exchange.direct_debit.exceptions import ThirdPartyAuthenticatorError
from exchange.direct_debit.integrations.faraboom import FaraboomAuthenticator
from tests.direct_debit.helper import DirectDebitMixins


class FaraboomLoginTest(DirectDebitMixins, TestCase):
    fixtures = ('test_data',)

    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.authenticator = FaraboomAuthenticator()
        self.metric_name = 'login_/oauth/token'

    @responses.activate
    def test_login(self):
        responses.post(
            url=f'{self.base_url}/oauth/token',
            json={
                'access_token': 'qXih0dLJLjBbxmmqmYIcQLGHInzRZym3RdKvtEf74Q2HXUkvwqJQjOmivjJQNdtoC988ZcVxCY2zkwYZcYMuRKo',
                'token_type': 'bearer',
                'scope': 'all',
                'expires_in': 6115900,
            },
            status=200,
        )

        self.authenticator.acquire_access_token()
        assert (
            self.authenticator.access_token
            == 'qXih0dLJLjBbxmmqmYIcQLGHInzRZym3RdKvtEf74Q2HXUkvwqJQjOmivjJQNdtoC988ZcVxCY2zkwYZcYMuRKo'
        )
        assert cache.get('metric_direct_debit_provider_calls__faraboom_auth_bank_Successful') == 1

    @responses.activate
    def test_login_failed_client_id_incorrect(self):
        responses.post(
            url=f'{self.base_url}/oauth/token',
            json={
                'error': 'خطای احراز هویت رخ داده است.',
                'code': '2009',
                'errors': [
                    {
                        'error': 'خطای احراز هویت رخ داده است.',
                        'code': '2009',
                    },
                ],
            },
            status=401,
        )

        with pytest.raises(ThirdPartyAuthenticatorError):
            self.authenticator.acquire_access_token()

        assert cache.get('metric_direct_debit_provider_calls__faraboom_auth_bank_Request401') == 1
