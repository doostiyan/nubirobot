from uuid import uuid4

from django.test import override_settings

from exchange.accounts.models import User, UserOTP, UserSms
from exchange.base.internal import idempotency
from exchange.base.internal.services import Services
from exchange.base.models import Settings
from tests.helpers import (
    APITestCaseWithIdempotency,
    InternalAPITestMixin,
    create_internal_token,
    mock_internal_service_settings,
)


class TestInternalSendOTP(InternalAPITestMixin, APITestCaseWithIdempotency):
    URL = '/internal/users/%s/send-otp'

    def setUp(self):
        self.user = User.objects.create_user(
            uid=uuid4(), username='test-user', mobile='09123334455', email='test@test.com', national_code='123456890'
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token(Services.ABC.value)}')
        vp = self.user.get_verification_profile()
        vp.email_confirmed = True
        vp.mobile_confirmed = True
        vp.identity_confirmed = True
        vp.mobile_identity_confirmed = True
        vp.save()

    def _request(self, uid=None, otp_type=None, otp_usage=None, headers=None):
        uid = uid or self.user.uid
        data = {}
        if otp_type is not None:
            data.update({'otpType': otp_type})

        if otp_usage is not None:
            data.update({'otpUsage': otp_usage})
        return self.client.post(self.URL % uid, data=data, headers=headers or {})

    def assert_failed(self, response, status_code, body):
        assert response.status_code == status_code
        assert response.json() == body
        assert (
            UserSms.objects.filter(
                user=self.user,
                tp=UserSms.TYPES.grant_financial_service,
                to=self.user.mobile,
                template=UserSms.TEMPLATES.grant_financial_service,
            ).count()
            == 0
        )
        assert (
            UserOTP.active_otps(
                user=self.user,
                tp=UserOTP.OTP_TYPES.mobile,
                usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
            ).count()
            == 0
        )

    @mock_internal_service_settings
    def test_internal_send_otp(self):
        otp_type = 'mobile'
        otp_usage = 'grant_permission_to_financial_service'
        response = self._request(otp_type=otp_type, otp_usage=otp_usage)

        assert response.status_code == 200, response.json()
        assert response.json() == {}
        otp_q = UserOTP.active_otps(
            user=self.user,
            tp=UserOTP.OTP_TYPES.mobile,
            usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
        )
        assert otp_q.count() == 1
        otp = otp_q.first()
        sms_q = UserSms.objects.filter(
            user=self.user,
            tp=UserSms.TYPES.grant_financial_service,
            to=self.user.mobile,
            text=otp.code,
            template=UserSms.TEMPLATES.grant_financial_service,
        )
        assert sms_q.count() == 1

        response = self._request(otp_type=otp_type, otp_usage=otp_usage)
        assert otp_q.count() == 1
        assert sms_q.count() == 2

    @mock_internal_service_settings
    def test_internal_send_otp_idempotency(self):
        otp_type = 'mobile'
        otp_usage = 'grant_permission_to_financial_service'
        idempotency_key = str(uuid4())
        response = self._request(
            otp_type=otp_type,
            otp_usage=otp_usage,
            headers={
                idempotency.IDEMPOTENCY_HEADER: idempotency_key,
            },
        )
        assert response.status_code == 200, response.json()
        assert response.json() == {}
        otp_q = UserOTP.active_otps(
            user=self.user,
            tp=UserOTP.OTP_TYPES.mobile,
            usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
        )
        assert otp_q.count() == 1
        otp = otp_q.first()
        sms_q = UserSms.objects.filter(
            user=self.user,
            tp=UserSms.TYPES.grant_financial_service,
            to=self.user.mobile,
            text=otp.code,
            template=UserSms.TEMPLATES.grant_financial_service,
        )
        assert sms_q.count() == 1

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
        assert otp_q.count() == 1
        assert sms_q.count() == 1

    @override_settings(RATELIMIT_ENABLE=True)
    @mock_internal_service_settings
    def test_internal_send_otp_ratelimit(self):
        otp_type = 'mobile'
        otp_usage = 'grant_permission_to_financial_service'
        for _ in range(3):
            response = self._request(otp_type=otp_type, otp_usage=otp_usage)

        assert response.status_code == 429
        assert response.json() == {
            'status': 'failed',
            'message': 'تعداد درخواست شما بیش از حد معمول تشخیص داده شده. لطفا کمی صبر نمایید.',
            'code': 'TooManyRequests',
        }
        assert (
            UserSms.objects.filter(
                user=self.user,
                tp=UserSms.TYPES.grant_financial_service,
                to=self.user.mobile,
                template=UserSms.TEMPLATES.grant_financial_service,
            ).count()
            == 2
        )
        assert (
            UserOTP.active_otps(
                user=self.user,
                tp=UserOTP.OTP_TYPES.mobile,
                usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
            ).count()
            == 1
        )

    @override_settings(IS_TESTNET=True)
    @mock_internal_service_settings
    def test_internal_send_otp_testnet(self):
        Settings.set('internal_ip_whitelist', ['127.0.0.1'])
        otp_type = 'mobile'
        otp_usage = 'grant_permission_to_financial_service'
        response = self._request(otp_type=otp_type, otp_usage=otp_usage)

        assert response.status_code == 200

    @mock_internal_service_settings
    def test_internal_send_otp_without_confirmed_mobile(self):
        vp = self.user.get_verification_profile()
        vp.mobile_confirmed = False
        vp.save(update_fields=('mobile_confirmed',))

        otp_type = 'mobile'
        otp_usage = 'grant_permission_to_financial_service'
        response = self._request(otp_type=otp_type, otp_usage=otp_usage)
        self.assert_failed(
            response,
            400,
            {
                'status': 'failed',
                'message': 'User has not confirmed mobile',
                'code': 'MobileNotConfirmed',
            },
        )

    @mock_internal_service_settings
    def test_internal_send_otp_user_invalid_otp_type(self):
        otp_type = 'invalid'
        otp_usage = 'grant_permission_to_financial_service'
        response = self._request(otp_type=otp_type, otp_usage=otp_usage)
        self.assert_failed(
            response,
            400,
            {'status': 'failed', 'message': 'Invalid choices: "invalid"', 'code': 'ParseError'},
        )

    @mock_internal_service_settings
    def test_internal_send_otp_user_invalid_otp_usage(self):
        otp_type = 'mobile'
        otp_usage = 'invalid'
        response = self._request(otp_type=otp_type, otp_usage=otp_usage)
        self.assert_failed(
            response,
            400,
            {'status': 'failed', 'message': 'Invalid choices: "invalid"', 'code': 'ParseError'},
        )

    @mock_internal_service_settings
    def test_internal_send_otp_user_missing_otp_usage(self):
        otp_type = 'mobile'
        response = self._request(otp_type=otp_type)
        self.assert_failed(
            response,
            400,
            {'status': 'failed', 'message': 'Missing choices value', 'code': 'ParseError'},
        )

    @mock_internal_service_settings
    def test_internal_send_otp_user_missing_otp_type(self):
        otp_type = 'mobile'
        response = self._request(otp_type=otp_type)
        self.assert_failed(
            response,
            400,
            {'status': 'failed', 'message': 'Missing choices value', 'code': 'ParseError'},
        )

    @mock_internal_service_settings
    def test_internal_send_otp_user_not_found(self):
        otp_type = 'mobile'
        otp_usage = 'grant_permission_to_financial_service'
        response = self._request(str(uuid4()), otp_type=otp_type, otp_usage=otp_usage)
        self.assert_failed(response, 404, {'message': 'User not found', 'error': 'NotFound'})

    @mock_internal_service_settings
    def test_internal_send_otp_invalid_uuid(self):
        response = self._request('invalid-uuid')
        assert response.status_code == 404

    @mock_internal_service_settings
    def test_internal_send_otp_token_without_permission(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token("notification")}')
        response = self._request()
        self.assert_failed(response, 404, {'detail': 'یافت نشد.'})
