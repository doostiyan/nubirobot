import uuid

import responses
from django.test import TestCase
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.externals.base import NOBITEX_BASE_URL
from exchange.asset_backed_credit.externals.otp import OTPProvider
from exchange.base.models import Settings


class OTPProviderTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(id=201)
        self.otp_type = OTPProvider.OTP_TYPES.mobile
        self.otp_usage = OTPProvider.OTP_USAGE.grant_permission_to_financial_service
        self.otp_code = '123456'

        self.send_internal_api_url = f'{NOBITEX_BASE_URL}/internal/users/{self.user.uid}/send-otp'
        self.verify_internal_api_url = f'{NOBITEX_BASE_URL}/internal/users/{self.user.uid}/verify-otp'

    @responses.activate
    def test_send_otp_success_when_internal_api_is_enabled(self):
        responses.post(
            url=self.send_internal_api_url,
            json={},
            status=status.HTTP_200_OK,
        )
        Settings.set('abc_use_send_otp_internal_api', 'yes')

        response_status = OTPProvider().send_otp_with_internal_api(
            self.user, self.otp_type, self.otp_usage, idempotency=uuid.uuid4()
        )
        assert response_status == status.HTTP_200_OK

    @responses.activate
    def test_send_otp_when_internal_api_is_enabled_but_raises_error(self):
        responses.post(
            url=self.send_internal_api_url,
            json={},
            status=status.HTTP_400_BAD_REQUEST,
        )
        Settings.set('abc_use_send_otp_internal_api', 'yes')

        response_status = OTPProvider().send_otp_with_internal_api(
            self.user, self.otp_type, self.otp_usage, idempotency=uuid.uuid4()
        )
        assert response_status == status.HTTP_400_BAD_REQUEST

    @responses.activate
    def test_verify_otp_when_internal_api_is_enabled(self):
        responses.post(
            url=self.verify_internal_api_url,
            json={},
            status=status.HTTP_200_OK,
        )
        Settings.set('abc_use_verify_otp_internal_api', 'yes')

        response_status = OTPProvider().verify_otp_with_internal_api(
            self.user, self.otp_type, self.otp_usage, self.otp_code, idempotency=uuid.uuid4()
        )
        assert response_status == status.HTTP_200_OK

    @responses.activate
    def test_verify_otp_when_internal_api_is_enabled_but_raises_error(self):
        responses.post(
            url=self.verify_internal_api_url,
            json={},
            status=status.HTTP_400_BAD_REQUEST,
        )
        Settings.set('abc_use_verify_otp_internal_api', 'yes')

        response_status = OTPProvider().verify_otp_with_internal_api(
            self.user, self.otp_type, self.otp_usage, self.otp_code, idempotency=uuid.uuid4()
        )
        assert response_status == status.HTTP_400_BAD_REQUEST
