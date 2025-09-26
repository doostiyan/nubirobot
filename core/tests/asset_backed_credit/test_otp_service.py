from datetime import timedelta

import pytest
import responses
from django.test import TestCase
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import OTPProviderError, OTPValidationError
from exchange.asset_backed_credit.externals.base import NOBITEX_BASE_URL
from exchange.asset_backed_credit.externals.otp import OTPProvider
from exchange.asset_backed_credit.models import InternalUser
from exchange.asset_backed_credit.models.otp import OTPLog
from exchange.asset_backed_credit.services.otp import send_otp, verify_otp
from exchange.base.calendar import ir_now
from exchange.base.models import Settings


class SendOTPServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(id=201)
        self.internal_user = InternalUser.create(self.user.uid)
        self.otp_type = OTPProvider.OTP_TYPES.mobile
        self.otp_usage = OTPProvider.OTP_USAGE.grant_permission_to_financial_service
        self.send_internal_api_url = f'{NOBITEX_BASE_URL}/internal/users/{self.user.uid}/send-otp'

    @responses.activate
    def test_send_otp_success_when_internal_api_is_enabled(self):
        responses.post(
            url=self.send_internal_api_url,
            json={},
            status=status.HTTP_200_OK,
        )
        Settings.set('abc_use_send_otp_internal_api', 'yes')
        send_otp(self.user, self.otp_type, self.otp_usage)

        log = OTPLog.objects.get(user=self.user, otp_type=self.otp_type, usage=self.otp_usage)
        assert log.send_api_response_code == status.HTTP_200_OK
        assert log.send_api_called_at
        assert log.verify_api_response_code is None
        assert log.verify_api_called_at is None
        assert log.internal_user.id

    @responses.activate
    def test_send_otp_fails_when_internal_api_is_enabled_but_raises_error(self):
        responses.post(
            url=self.send_internal_api_url,
            json={},
            status=status.HTTP_400_BAD_REQUEST,
        )
        Settings.set('abc_use_send_otp_internal_api', 'yes')

        with pytest.raises(OTPProviderError):
            send_otp(self.user, self.otp_type, self.otp_usage)

        log = OTPLog.objects.get(user=self.user, otp_type=self.otp_type, usage=self.otp_usage)
        assert log.send_api_response_code == status.HTTP_400_BAD_REQUEST
        assert log.send_api_called_at
        assert log.verify_api_response_code is None
        assert log.verify_api_called_at is None
        assert log.internal_user.id

    @responses.activate
    def test_send_otp_when_internal_api_is_enabled_and_exists_internally_failed_otp_log_then_send_otp_updates_existing_log(
        self,
    ):
        responses.post(
            url=self.send_internal_api_url,
            json={},
            status=status.HTTP_200_OK,
        )
        Settings.set('abc_use_send_otp_internal_api', 'yes')
        log = OTPLog.objects.create(
            user=self.user,
            internal_user=self.internal_user,
            otp_type=self.otp_type,
            usage=self.otp_usage,
            send_api_response_code=status.HTTP_400_BAD_REQUEST,
            send_api_called_at=ir_now(),
        )

        send_otp(self.user, self.otp_type, self.otp_usage)

        log.refresh_from_db()
        assert log.send_api_response_code == status.HTTP_200_OK
        assert log.send_api_called_at
        assert log.verify_api_response_code is None
        assert log.verify_api_called_at is None
        assert log.internal_user.id

    @responses.activate
    def test_send_otp_when_internal_api_is_enabled_and_user_has_verified_log_then_create_new_log_for_it(self):
        responses.post(
            url=self.send_internal_api_url,
            json={},
            status=status.HTTP_200_OK,
        )
        Settings.set('abc_use_send_otp_internal_api', 'yes')
        verified_log = OTPLog.objects.create(
            user=self.user,
            internal_user=self.internal_user,
            otp_type=self.otp_type,
            usage=self.otp_usage,
            send_api_response_code=status.HTTP_200_OK,
            verify_api_response_code=status.HTTP_200_OK,
            send_api_called_at=ir_now(),
            verify_api_called_at=ir_now(),
        )

        send_otp(self.user, self.otp_type, self.otp_usage)

        log = (
            OTPLog.objects.filter(user=self.user, otp_type=self.otp_type, usage=self.otp_usage)
            .order_by('-created_at')
            .first()
        )
        assert log.id != verified_log.id
        assert log.send_api_response_code == status.HTTP_200_OK
        assert log.send_api_called_at
        assert log.verify_api_response_code is None
        assert log.verify_api_called_at is None
        assert log.internal_user.id


class VerifyOTPServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(id=201)
        self.internal_user = InternalUser.create(self.user.uid)
        self.otp_code = '123456'
        self.otp_type = OTPProvider.OTP_TYPES.mobile
        self.otp_usage = OTPProvider.OTP_USAGE.grant_permission_to_financial_service
        self.verify_internal_api_url = f'{NOBITEX_BASE_URL}/internal/users/{self.user.uid}/verify-otp'

    @responses.activate
    def test_verify_otp_service_when_internal_api_is_enabled_then_otp_log_updates_successfully(self):
        responses.post(
            url=self.verify_internal_api_url,
            json={},
            status=status.HTTP_200_OK,
        )
        Settings.set('abc_use_verify_otp_internal_api', 'yes')
        log = OTPLog.objects.create(
            user=self.user,
            internal_user=self.internal_user,
            otp_type=self.otp_type,
            usage=self.otp_usage,
            send_api_response_code=status.HTTP_200_OK,
            send_api_called_at=ir_now(),
        )

        assert log.verify_api_called_at is None
        assert log.verify_api_response_code is None
        assert log.internal_user.id

        verify_otp(self.user, self.otp_type, self.otp_usage, self.otp_code)

        log.refresh_from_db()
        assert log.verify_api_called_at
        assert log.verify_api_response_code == status.HTTP_200_OK
        assert log.internal_user.id

    @responses.activate
    def test_verify_otp_fails_when_internal_api_is_enabled_but_raises_error(self):
        responses.post(
            url=self.verify_internal_api_url,
            json={},
            status=status.HTTP_400_BAD_REQUEST,
        )
        Settings.set('abc_use_verify_otp_internal_api', 'yes')
        log = OTPLog.objects.create(
            user=self.user,
            internal_user=self.internal_user,
            otp_type=self.otp_type,
            usage=self.otp_usage,
            send_api_response_code=status.HTTP_200_OK,
            send_api_called_at=ir_now(),
        )

        assert log.verify_api_called_at is None
        assert log.verify_api_response_code is None
        assert log.internal_user.id

        with pytest.raises(OTPValidationError):
            verify_otp(self.user, self.otp_type, self.otp_usage, self.otp_code)

        log.refresh_from_db()
        assert log.verify_api_called_at
        assert log.internal_user.id
        assert log.verify_api_response_code == status.HTTP_400_BAD_REQUEST

    def test_verify_otp_fails_when_internal_api_is_enabled_but_user_has_no_otp_log_instance(self):
        Settings.set('abc_use_verify_otp_internal_api', 'yes')
        with pytest.raises(OTPValidationError):
            verify_otp(self.user, self.otp_type, self.otp_usage, self.otp_code)

    def test_verify_otp_fails_when_internal_api_is_enabled_but_user_has_no_otp_log_in_the_last_thirty_minutes(self):
        log = OTPLog.objects.create(
            user=self.user,
            internal_user=self.internal_user,
            otp_type=self.otp_type,
            usage=self.otp_usage,
            send_api_response_code=status.HTTP_200_OK,
            send_api_called_at=ir_now(),
        )
        log.created_at = ir_now() - timedelta(minutes=31)
        log.save()

        Settings.set('abc_use_verify_otp_internal_api', 'yes')
        with pytest.raises(OTPValidationError):
            verify_otp(self.user, self.otp_type, self.otp_usage, self.otp_code)

        log.refresh_from_db()
        assert log.verify_api_called_at is None
        assert log.verify_api_response_code is None
        assert log.internal_user.id

    def test_verify_otp_fails_when_internal_api_is_enabled_but_user_has_otp_log_that_has_none_200_status_in_send_api_status(
        self,
    ):
        log = OTPLog.objects.create(
            user=self.user,
            internal_user=self.internal_user,
            otp_type=self.otp_type,
            usage=self.otp_usage,
            send_api_response_code=status.HTTP_400_BAD_REQUEST,
            send_api_called_at=ir_now(),
        )
        Settings.set('abc_use_verify_otp_internal_api', 'yes')
        with pytest.raises(OTPValidationError):
            verify_otp(self.user, self.otp_type, self.otp_usage, self.otp_code)

        log.refresh_from_db()
        assert log.verify_api_called_at is None
        assert log.verify_api_response_code is None
        assert log.internal_user.id

    def test_verify_otp_fails_when_internal_api_is_enabled_but_user_has_otp_log_with_send_api_called_at_is_none(self):
        log = OTPLog.objects.create(
            user=self.user, internal_user=self.internal_user, otp_type=self.otp_type, usage=self.otp_usage
        )
        assert log.send_api_called_at is None
        assert log.send_api_response_code is None
        assert log.internal_user.id

        Settings.set('abc_use_verify_otp_internal_api', 'yes')
        with pytest.raises(OTPValidationError):
            verify_otp(self.user, self.otp_type, self.otp_usage, self.otp_code)

        log.refresh_from_db()
        assert log.verify_api_called_at is None
        assert log.verify_api_response_code is None
        assert log.internal_user.id
