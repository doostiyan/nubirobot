from django.test.testcases import TestCase

from exchange.accounts.models import User, UserOTP, UserSms
from exchange.marketing.exceptions import InvalidOTPException
from exchange.marketing.services.otp import send_sms_otp, verify_sms_otp


class TestCampaignOTP(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)

    def tearDown(self):
        UserOTP.objects.all().delete()
        UserSms.objects.all().delete()

    def test_send_sms_otp_when_user_does_not_exist_success(self):
        # given ->
        mobile_number = '09123456789'
        usage = UserOTP.OTP_Usage.campaign

        # when->
        send_sms_otp(mobile_number, usage)

        # then->
        otp = UserOTP.objects.filter(phone_number=mobile_number).first()
        user_sms = UserSms.objects.filter(to=mobile_number).first()
        self.assert_sms_and_otp(otp, user_sms, mobile_number)
        assert otp.user is None
        assert user_sms.user is None

    def test_send_sms_otp_when_user_exists_success(self):
        # given ->
        self.user.mobile = '09123456789'
        self.user.save(update_fields=['mobile'])
        usage = UserOTP.OTP_Usage.campaign

        # when->
        send_sms_otp(self.user.mobile, usage)

        # then->
        otp = UserOTP.objects.filter(phone_number=self.user.mobile).first()
        user_sms = UserSms.objects.filter(to=self.user.mobile).first()
        self.assert_sms_and_otp(otp, user_sms, self.user.mobile)
        assert otp.user == self.user
        assert user_sms.user == self.user

    @staticmethod
    def assert_sms_and_otp(otp, user_sms, mobile_number):
        assert otp
        assert otp.otp_type == UserOTP.OTP_TYPES.mobile
        assert otp.otp_usage == UserOTP.OTP_Usage.campaign
        assert otp.otp_status == UserOTP.OTP_STATUS.new
        assert otp.code
        assert otp.is_sent
        assert otp.phone_number == mobile_number

        assert user_sms
        assert user_sms.text
        assert user_sms.to == mobile_number

    def test_verify_sms_otp_when_code_is_invalid_error(self):
        # given ->
        mobile_number = '09123456789'
        usage = UserOTP.OTP_Usage.campaign
        send_sms_otp(mobile_number, usage)
        otp = UserOTP.objects.filter(phone_number=mobile_number).first()

        # when->
        with self.assertRaises(InvalidOTPException) as context:
            verify_sms_otp(mobile_number, 'wrong_code', usage)

        # then->
        self.assertEqual(str(context.exception), 'not found')

    def test_verify_sms_otp_when_user_does_not_exist_success(self):
        # given ->
        mobile_number = '09123456789'
        usage = UserOTP.OTP_Usage.campaign
        send_sms_otp(mobile_number, usage)
        otp = UserOTP.objects.filter(phone_number=mobile_number).first()

        # when->
        user, phone_number = verify_sms_otp(mobile_number, otp.code, usage)

        # then->
        assert user is None
        assert phone_number == mobile_number

    def test_verify_sms_otp_when_user_exists_success(self):
        # given ->
        self.user.mobile = '09123456789'
        self.user.save(update_fields=['mobile'])
        usage = UserOTP.OTP_Usage.campaign
        send_sms_otp(self.user.mobile, usage)
        otp = UserOTP.objects.filter(phone_number=self.user.mobile).first()

        # when->
        user, phone_number = verify_sms_otp(self.user.mobile, otp.code, usage)

        # then->
        assert user == self.user
        assert phone_number == self.user.mobile
