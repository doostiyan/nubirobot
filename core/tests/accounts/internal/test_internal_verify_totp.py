import uuid
from unittest.mock import patch

from exchange.accounts.models import User
from exchange.base.internal.services import Services
from tests.helpers import (
    APITestCaseWithIdempotency,
    InternalAPITestMixin,
    create_internal_token,
    mock_internal_service_settings,
)


class TestInternalVerifyTOTP(InternalAPITestMixin, APITestCaseWithIdempotency):
    URL = '/internal/users/%s/verify-totp'

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token(Services.ABC.value)}')

    def _request(self, uid=None, totp=None, headers=None):
        uid = uid or self.user.uid
        data = {}

        if totp:
            data.update({'totp': totp})

        return self.client.post(self.URL % uid, data=data, headers=headers or {})

    @mock_internal_service_settings
    @patch('exchange.accounts.views.internal.check_user_otp', return_value=True)
    def test_internal_verify_correct_totp(self, totp_mock):

        response = self._request(totp='correct totp')

        assert response.status_code == 200, response.json()
        assert response.json() == {}

    @mock_internal_service_settings
    @patch('exchange.accounts.views.internal.check_user_otp', return_value=False)
    def test_internal_verify_wrong_totp(self, totp_mock):

        response = self._request(totp='wrong totp')

        assert response.status_code == 422, response.json()
        assert response.json() == {
            'status': 'failed',
            'message': 'TOTP is wrong',
            'code': 'wrongTotp',
        }

    @mock_internal_service_settings
    def test_internal_verify_totp_missing_totp(self):
        response = self._request()

        assert response.status_code == 400, response.json()
        assert response.json() == {'code': 'ParseError', 'message': 'Missing string value', 'status': 'failed'}

    @mock_internal_service_settings
    def test_internal_verify_totp_missing_totp(self):
        response = self._request(uid=uuid.uuid4(), totp='wrong totp')
        assert response.status_code == 404, response.json()
        assert response.json() == {'message': 'User not found', 'code': 'notFound', 'status': 'failed'}
