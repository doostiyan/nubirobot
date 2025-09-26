from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.test import override_settings

from exchange.accounts.models import User, UserOTP
from exchange.base.internal import idempotency
from exchange.base.internal.services import Services
from tests.helpers import (
    APITestCaseWithIdempotency,
    InternalAPITestMixin,
    create_internal_token,
    mock_internal_service_settings,
)


class TestInternalVerifyOTP(InternalAPITestMixin, APITestCaseWithIdempotency):
    URL = '/internal/users/%s/verify-otp'

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        cls.opt_obj = UserOTP.create_otp(
            user=cls.user,
            tp=UserOTP.OTP_TYPES.mobile,
            usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
        )

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token(Services.ABC.value)}')

    def _request(self, uid=None, code=None, otp_type=None, otp_usage=None, headers=None):
        uid = uid or self.user.uid
        data = {}
        if otp_type is not None:
            data.update({'otpType': otp_type})

        if otp_usage is not None:
            data.update({'otpUsage': otp_usage})

        if code:
            data.update({'otpCode': code})

        return self.client.post(self.URL % uid, data=data, headers=headers or {})

    def assert_failed(self, response, status_code, body):
        assert response.status_code == status_code
        assert response.json() == body
        assert (
            UserOTP.objects.filter(
                user=self.user,
                otp_type=UserOTP.OTP_TYPES.mobile,
                otp_usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
                otp_status=UserOTP.OTP_STATUS.used,
            ).count()
            == 0
        )

    @mock_internal_service_settings
    def test_internal_verify_otp(self):
        otp_type = 'mobile'
        otp_usage = 'grant_permission_to_financial_service'
        response = self._request(code=self.opt_obj.code, otp_type=otp_type, otp_usage=otp_usage)

        assert response.status_code == 200, response.json()
        assert response.json() == {}
        otp_q = UserOTP.objects.filter(
            user=self.user,
            otp_type=UserOTP.OTP_TYPES.mobile,
            otp_usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
        )
        assert otp_q.count() == 1
        assert otp_q.first().otp_status == UserOTP.OTP_STATUS.used

    @mock_internal_service_settings
    def test_internal_verify_otp_already_used(self):
        self.opt_obj.otp_status = UserOTP.OTP_STATUS.used
        self.opt_obj.save(update_fields=('otp_status',))

        otp_type = 'mobile'
        otp_usage = 'grant_permission_to_financial_service'
        response = self._request(code=self.opt_obj.code, otp_type=otp_type, otp_usage=otp_usage)

        assert response.status_code == 400
        assert response.json() == {
            'status': 'failed',
            'message': 'OTP does not verified: already used',
            'code': 'alreadyUsed',
        }

    @mock_internal_service_settings
    def test_internal_verify_otp_disabled(self):
        self.opt_obj.otp_status = UserOTP.OTP_STATUS.disabled
        self.opt_obj.save(update_fields=('otp_status',))

        otp_type = 'mobile'
        otp_usage = 'grant_permission_to_financial_service'
        response = self._request(code=self.opt_obj.code, otp_type=otp_type, otp_usage=otp_usage)

        self.assert_failed(
            response,
            400,
            {
                'status': 'failed',
                'message': 'OTP does not verified: disabled',
                'code': 'disabled',
            },
        )

    @mock_internal_service_settings
    def test_internal_verify_otp_expired(self):
        self.opt_obj.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.opt_obj.save(update_fields=('expires_at',))

        otp_type = 'mobile'
        otp_usage = 'grant_permission_to_financial_service'
        response = self._request(code=self.opt_obj.code, otp_type=otp_type, otp_usage=otp_usage)

        self.assert_failed(
            response,
            400,
            {
                'status': 'failed',
                'message': 'OTP does not verified: expired',
                'code': 'expired',
            },
        )

    @mock_internal_service_settings
    def test_internal_verify_otp_not_found(self):
        otp_type = 'phone'
        otp_usage = 'grant_permission_to_financial_service'
        response = self._request(code=self.opt_obj.code, otp_type=otp_type, otp_usage=otp_usage)

        self.assert_failed(
            response,
            400,
            {
                'status': 'failed',
                'message': 'OTP does not verified: not found',
                'code': 'notFound',
            },
        )

    @mock_internal_service_settings
    def test_internal_verify_otp_incorrect_code(self):
        otp_type = 'phone'
        otp_usage = 'grant_permission_to_financial_service'
        response = self._request(code='-1', otp_type=otp_type, otp_usage=otp_usage)

        self.assert_failed(
            response,
            400,
            {
                'status': 'failed',
                'message': 'OTP does not verified: not found',
                'code': 'notFound',
            },
        )

    @mock_internal_service_settings
    def test_internal_verify_otp_idempotency(self):
        otp_type = 'mobile'
        otp_usage = 'grant_permission_to_financial_service'
        idempotency_key = str(uuid4())
        response = self._request(
            code=self.opt_obj.code,
            otp_type=otp_type,
            otp_usage=otp_usage,
            headers={
                idempotency.IDEMPOTENCY_HEADER: idempotency_key,
            },
        )
        assert response.status_code == 200, response.json()
        assert response.json() == {}
        otp_q = UserOTP.objects.filter(
            user=self.user,
            otp_type=UserOTP.OTP_TYPES.mobile,
            otp_usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
        )
        assert otp_q.count() == 1
        assert otp_q.first().otp_status == UserOTP.OTP_STATUS.used

        # Make a duplicate request, expecting the same result
        response = self._request(
            otp_type=otp_type,
            otp_usage=otp_usage,
            headers={
                idempotency.IDEMPOTENCY_HEADER: idempotency_key,
            },
        )
        assert response.status_code == 200, response.json()
        assert response.json() == {}
        otp_q = UserOTP.objects.filter(
            user=self.user,
            otp_type=UserOTP.OTP_TYPES.mobile,
            otp_usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
        )
        assert otp_q.count() == 1
        assert otp_q.first().otp_status == UserOTP.OTP_STATUS.used

    @override_settings(RATELIMIT_ENABLE=True)
    @mock_internal_service_settings
    def test_internal_verify_otp_ratelimit(self):
        otp_type = 'mobile'
        otp_usage = 'grant_permission_to_financial_service'
        for _ in range(4):
            response = self._request(code=self.opt_obj.code, otp_type=otp_type, otp_usage=otp_usage)

        assert response.status_code == 429
        assert response.json() == {
            'status': 'failed',
            'message': 'تعداد درخواست شما بیش از حد معمول تشخیص داده شده. لطفا کمی صبر نمایید.',
            'code': 'TooManyRequests',
        }
        assert (
            UserOTP.objects.filter(
                user=self.user,
                otp_type=UserOTP.OTP_TYPES.mobile,
                otp_usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
            ).count()
            == 1
        )

    @mock_internal_service_settings
    def test_internal_verify_otp_user_invalid_otp_usage(self):
        otp_type = 'mobile'
        otp_usage = 'invalid'
        response = self._request(code=self.opt_obj.code, otp_type=otp_type, otp_usage=otp_usage)
        self.assert_failed(
            response,
            400,
            {'status': 'failed', 'message': 'Invalid choices: "invalid"', 'code': 'ParseError'},
        )

    @mock_internal_service_settings
    def test_internal_verify_otp_user_invalid_otp_type(self):
        otp_type = 'invalid'
        otp_usage = 'grant_permission_to_financial_service'
        response = self._request(code=self.opt_obj.code, otp_type=otp_type, otp_usage=otp_usage)
        self.assert_failed(
            response,
            400,
            {'status': 'failed', 'message': 'Invalid choices: "invalid"', 'code': 'ParseError'},
        )

    @mock_internal_service_settings
    def test_internal_verify_otp_user_missing_otp_usage(self):
        otp_type = 'mobile'
        response = self._request(code=self.opt_obj.code, otp_type=otp_type)
        self.assert_failed(
            response,
            400,
            {'status': 'failed', 'message': 'Missing choices value', 'code': 'ParseError'},
        )

    @mock_internal_service_settings
    def test_internal_verify_otp_user_missing_otp_type(self):
        otp_type = 'mobile'
        response = self._request(code=self.opt_obj.code, otp_type=otp_type)
        self.assert_failed(
            response,
            400,
            {'status': 'failed', 'message': 'Missing choices value', 'code': 'ParseError'},
        )

    @mock_internal_service_settings
    def test_internal_verify_otp_user_missing_otp_code(self):
        otp_type = 'mobile'
        otp_usage = 'grant_permission_to_financial_service'
        response = self._request(otp_usage=otp_usage, otp_type=otp_type)
        self.assert_failed(
            response,
            400,
            {'status': 'failed', 'message': 'Missing string value', 'code': 'ParseError'},
        )

    @mock_internal_service_settings
    def test_internal_verify_otp_user_not_found(self):
        otp_type = 'mobile'
        otp_usage = 'grant_permission_to_financial_service'
        response = self._request(uid=str(uuid4()), code=self.opt_obj.code, otp_type=otp_type, otp_usage=otp_usage)
        self.assert_failed(response, 404, {'message': 'User not found', 'error': 'NotFound'})

    @mock_internal_service_settings
    def test_internal_verify_otp_invalid_uuid(self):
        response = self._request(uid='invalid-uuid')
        assert response.status_code == 404

    @mock_internal_service_settings
    def test_internal_verify_otp_token_without_permission(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token("notification")}')
        response = self._request()
        self.assert_failed(response, 404, {'detail': 'یافت نشد.'})
