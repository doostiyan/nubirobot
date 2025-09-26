from unittest.mock import patch

from django.test import TestCase

from exchange.accounts.kyc_param_notifier import KYCParam
from exchange.accounts.models import User, UserSms, VerificationRequest
from exchange.base.calendar import ir_now
from exchange.security.models import KnownDevice
from tests.base.utils import mock_on_commit


def mock_confirmed_mobile(user):
    user.mobile = '09151234567'
    user.save()
    vp = user.get_verification_profile()
    vp.mobile_confirmed = True
    vp.save()


class TestKYCParamSMS(TestCase):
    def setUp(self):
        self.user: User = User.objects.get(pk=201)

    def confirm_or_reject_kyc_parameter(self, kyc_parameter: KYCParam, confirmed: bool):
        if kyc_parameter == KYCParam.SELFIE:
            vr = VerificationRequest.objects.create(
                tp=VerificationRequest.TYPES.selfie,
                user=self.user,
                status=VerificationRequest.STATUS.new,
            )
            vr.status = VerificationRequest.STATUS.confirmed if confirmed else VerificationRequest.STATUS.rejected
            vr.save()
        elif kyc_parameter == KYCParam.AUTO_KYC:
            if confirmed:
                self.user.do_verify_liveness_alpha()
            else:
                vr = VerificationRequest.objects.create(
                    tp=VerificationRequest.TYPES.auto_kyc,
                    user=self.user,
                    status=VerificationRequest.STATUS.new
                )
                vr.status = VerificationRequest.STATUS.rejected
                vr.save()
        elif kyc_parameter == KYCParam.IDENTITY:
            if confirmed:
                vp = self.user.get_verification_profile()
                vp.identity_confirmed = True
                vp.save()
            else:
                vr = VerificationRequest.objects.create(
                    tp=VerificationRequest.TYPES.identity,
                    user=self.user,
                    status=VerificationRequest.STATUS.new
                )
                vr.status = VerificationRequest.STATUS.rejected
                vr.updating_from_cron = True
                vr.save()
        else:
            raise Exception('not handled ')

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_no_confirmed_sms_for_kyc_params_since_no_mobile(self, _):
        previous_messages = UserSms.objects.count()
        self.confirm_or_reject_kyc_parameter(KYCParam.SELFIE, True)
        assert UserSms.objects.count() - previous_messages == 0
        self.confirm_or_reject_kyc_parameter(KYCParam.AUTO_KYC, True)
        assert UserSms.objects.count() - previous_messages == 0

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_no_rejcted_sms_for_kyc_params_since_no_mobile(self, _):
        previous_messages = UserSms.objects.count()
        self.confirm_or_reject_kyc_parameter(KYCParam.SELFIE, False)
        assert UserSms.objects.count() - previous_messages == 0
        self.confirm_or_reject_kyc_parameter(KYCParam.AUTO_KYC, False)
        assert UserSms.objects.count() - previous_messages == 0

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_confirmed_sms_for_kyc_params(self, _):
        mock_confirmed_mobile(self.user)
        previous_messages = UserSms.objects.count()
        self.confirm_or_reject_kyc_parameter(KYCParam.SELFIE, True)
        assert UserSms.objects.count() - previous_messages == 1
        assert 'احرازهویت سطح دو شما' in UserSms.objects.filter(user=self.user).last().text
        previous_messages = UserSms.objects.count()
        self.confirm_or_reject_kyc_parameter(KYCParam.AUTO_KYC, True)
        assert UserSms.objects.count() - previous_messages == 1
        assert 'احرازهویت سطح دو شما' in UserSms.objects.filter(user=self.user).last().text

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_rejcted_sms_for_kyc_params(self, _):
        mock_confirmed_mobile(self.user)
        previous_messages = UserSms.objects.count()
        self.confirm_or_reject_kyc_parameter(KYCParam.SELFIE, False)
        assert UserSms.objects.count() - previous_messages == 1
        previous_messages = UserSms.objects.count()
        assert 'احراز هویت سطح دو نوبیتکس شما ناموفق' in UserSms.objects.filter(user=self.user).last().text
        self.confirm_or_reject_kyc_parameter(KYCParam.AUTO_KYC, False)
        assert UserSms.objects.count() - previous_messages == 1
        assert 'احراز هویت سطح دو نوبیتکس شما ناموفق' in UserSms.objects.filter(user=self.user).last().text
        previous_messages = UserSms.objects.count()
        self.confirm_or_reject_kyc_parameter(KYCParam.IDENTITY, False)
        assert UserSms.objects.count() - previous_messages == 1
        assert 'احراز هویت شما ناموفق بود' in UserSms.objects.filter(user=self.user).last().text


class TestKYCTemplateSMS(TestCase):
    def setUp(self):
        self.user: User = User.objects.get(pk=202)

    def test_new_device(self):
        previous_messages = UserSms.objects.count()
        KnownDevice.objects.create(
            name='test_device', user=self.user, device_id='123456', user_agent='Firefox 123',
            last_activity=ir_now(),
        )
        assert UserSms.objects.count() - previous_messages == 0
        mock_confirmed_mobile(self.user)
        KnownDevice.objects.create(
            name='test_device', user=self.user, device_id='1234567', user_agent='Firefox 1234',
            last_activity=ir_now(),
        )
        assert UserSms.objects.count() - previous_messages == 0

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_set_email_no_sms_since_no_mobile(self, _):
        previous_messages = UserSms.objects.count()
        self.user.do_verify_email()
        assert UserSms.objects.count() - previous_messages == 0

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_set_email(self, _):
        mock_confirmed_mobile(self.user)
        previous_messages = UserSms.objects.count()
        self.user.do_verify_email()
        assert UserSms.objects.count() - previous_messages == 1
        assert 'ایمیل' in UserSms.objects.filter(user=self.user).last().text
