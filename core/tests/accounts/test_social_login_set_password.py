from typing import Optional
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APITestCase

from exchange.accounts.models import User, UserOTP, VerificationProfile
from exchange.base.models import Settings


class SocialLoginTestData(APITestCase):
    def setUp(self) -> None:
        self.user: User = User.objects.get(pk=201)
        self.user.password = '!google'
        self.user.social_login_enabled = True
        self.user.save()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    non_social_password = 'bxzad44f^&fir3%dc,moa@@'

    def switch_to_non_social(self):
        self.user.social_login_enabled = False
        self.user.set_password(self.non_social_password)
        self.user.save(update_fields=['password', 'social_login_enabled', ])
        assert self.user.check_password(self.non_social_password)


class GetOTPForSocialLoginTest(SocialLoginTestData):
    get_otp_url = '/otp/request'

    def setUp(self) -> None:
        super().setUp()
        self.user.mobile = '09151234567'
        self.user.save(update_fields=['mobile'])
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(
            email_confirmed=True, mobile_confirmed=True
        )

    def _request_otp(self, **update):
        data = dict(usage='social_user_set_password')
        data.update(update)
        resp = self.client.get(self.get_otp_url, data)
        return resp

    def test_get_otp_for_not_social_login_user(self):
        self.switch_to_non_social()
        resp = self._request_otp()
        assert resp.json()['status'] == 'failed'
        assert resp.json()['code'] == 'invalidUsageForUser'

    @patch('exchange.security.signals.EmailManager.send_email')
    def test_get_otp_ignore_tp(self, _):
        assert not UserOTP.objects.filter(
            user=self.user, otp_type=User.OTP_TYPES.email, otp_usage=UserOTP.OTP_Usage.social_user_set_password
        ).exists()
        assert not UserOTP.objects.filter(
            user=self.user, otp_type=User.OTP_TYPES.mobile, otp_usage=UserOTP.OTP_Usage.social_user_set_password
        ).exists()

        resp = self._request_otp(tp='mobile')
        assert resp.json()['status'] == 'ok'
        assert UserOTP.objects.filter(
            user=self.user, otp_type=User.OTP_TYPES.email, otp_usage=UserOTP.OTP_Usage.social_user_set_password
        ).exists()
        assert UserOTP.objects.filter(
            user=self.user, otp_type=User.OTP_TYPES.mobile, otp_usage=UserOTP.OTP_Usage.social_user_set_password
        ).exists()

        UserOTP.objects.filter(
            user=self.user, otp_usage=UserOTP.OTP_Usage.social_user_set_password
        ).delete()
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(mobile_confirmed=False)
        resp = self._request_otp(tp='mobile')
        assert resp.json()['status'] == 'ok'
        assert UserOTP.objects.filter(
            user=self.user, otp_type=User.OTP_TYPES.email, otp_usage=UserOTP.OTP_Usage.social_user_set_password
        ).exists()
        assert not UserOTP.objects.filter(
            user=self.user, otp_type=User.OTP_TYPES.mobile, otp_usage=UserOTP.OTP_Usage.social_user_set_password
        ).exists()

    @pytest.mark.slow
    @override_settings(POST_OFFICE={'BACKENDS': {'critical': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_send_email_on_something_accepted(self):
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')

        VerificationProfile.objects.filter(
            id=self.user.get_verification_profile().id
        ).update(mobile_confirmed=False)
        resp = self._request_otp()
        assert resp.json()['status'] == 'ok'
        assert UserOTP.objects.filter(
            user=self.user, otp_type=User.OTP_TYPES.email, otp_usage=UserOTP.OTP_Usage.social_user_set_password
        ).exists()
        assert not UserOTP.objects.filter(
            user=self.user, otp_type=User.OTP_TYPES.mobile, otp_usage=UserOTP.OTP_Usage.social_user_set_password
        ).exists()

        with patch('django.db.connection.close'):
            call_command('send_queued_mail')


class UserSocialLoginSetPasswordTest(SocialLoginTestData):
    set_password_url = '/auth/user/social-login-set-password'

    class OTPData:
        otp: str
        email_otp_object: Optional[UserOTP] = None
        mobile_otp_object: Optional[UserOTP] = None

        def __init__(self, user: User, email=True, mobile=False):

            self.otp = user.generate_otp(tp=User.OTP_TYPES.email)
            if email:
                self.email_otp_object = user.generate_otp_obj(
                    tp=User.OTP_TYPES.email, usage=UserOTP.OTP_Usage.social_user_set_password, otp=self.otp,
                )
            if mobile:
                self.mobile_otp_object = user.generate_otp_obj(
                    tp=User.OTP_TYPES.mobile, usage=UserOTP.OTP_Usage.social_user_set_password, otp=self.otp,
                )

        def __str__(self) -> str:
            return self.otp

    def _set_password(self, password, password_confirm: Optional[str] = None, otp: Optional[OTPData] = None):
        if otp is None:
            otp = self.OTPData(user=self.user)
        password_confirm = password_confirm or password
        resp = self.client.post(self.set_password_url, {
            "newPassword": password,
            "newPasswordConfirm": password_confirm,
            "otp": str(otp),
        })
        return resp

    def test_successfully_set_password(self):
        pw = 'cmfad@fcnir35evs%'
        assert not self.user.check_password(pw)
        resp = self._set_password(pw)
        assert resp.json()['status'] == 'ok'
        self.user.refresh_from_db()
        assert self.user.check_password(pw)
        with pytest.raises(User.auth_token.RelatedObjectDoesNotExist):
            self.user.auth_token

    def test_set_password_for_already_set_failed(self):
        pw1 = 'cmfad@fcnir35evs%'
        pw2 = 'bxzad44f^&fir3%dc,moa@@'
        self.user.set_password(pw1)
        self.user.save(update_fields=['password', ])
        assert self.user.check_password(pw1)
        resp = self._set_password(pw2)
        assert resp.json()['status'] == 'failed'
        assert resp.json()['code'] == 'canNotSetPassword'
        self.user.refresh_from_db()
        assert not self.user.check_password(pw2)
        assert self.user.check_password(pw1)

    def test_set_password_for_not_social_login_user(self):
        self.switch_to_non_social()
        pw2 = 'cmfad@fcnir35evs%'
        resp = self._set_password(pw2)
        assert resp.json()['status'] == 'failed'
        assert resp.json()['code'] == 'canNotSetPassword'
        self.user.refresh_from_db()
        assert not self.user.check_password(pw2)
        assert self.user.check_password(self.non_social_password)

    def test_set_password_unacceptable_password(self):
        pw = '123'
        resp = self._set_password(pw)
        resp_json = resp.json()
        assert resp_json['status'] == 'failed'
        assert resp_json['code'] == 'UnacceptablePassword'

        pw = 'cmfad@fcnir35evs%'
        resp = self._set_password(pw, pw[:-1] + 'x')
        resp_json = resp.json()
        assert resp_json['status'] == 'failed'
        assert resp_json['code'] == 'InvalidPasswordConfirm'

        assert not self.user.check_password(pw)
        assert self.user.can_social_login_user_set_password
        assert self.user.auth_token is not None

    def test_email_otp_gets_used(self):
        otp = self.OTPData(user=self.user, email=True, mobile=False)
        pw = 'cmfad@fcnir35evs%'
        assert not self.user.check_password(pw)
        assert otp.email_otp_object.otp_status != UserOTP.OTP_STATUS.used

        resp = self._set_password(pw, otp=otp)
        assert resp.json()['status'] == 'ok'
        self.user.refresh_from_db()
        assert self.user.check_password(pw)
        otp.email_otp_object.refresh_from_db()
        assert otp.email_otp_object.otp_status == UserOTP.OTP_STATUS.used

    def test_mobile_otp_gets_used(self):
        otp = self.OTPData(user=self.user, email=True, mobile=True)
        pw = 'cmfad@fcnir35evs%'
        assert not self.user.check_password(pw)
        assert otp.email_otp_object.otp_status != UserOTP.OTP_STATUS.used
        assert otp.mobile_otp_object.otp_status != UserOTP.OTP_STATUS.used

        resp = self._set_password(pw, otp=otp)
        assert resp.json()['status'] == 'ok'
        self.user.refresh_from_db()
        assert self.user.check_password(pw)
        otp.email_otp_object.refresh_from_db()
        otp.mobile_otp_object.refresh_from_db()
        assert otp.email_otp_object.otp_status == UserOTP.OTP_STATUS.used
        assert otp.mobile_otp_object.otp_status == UserOTP.OTP_STATUS.used

    def test_wrong_otp(self):
        otp = self.OTPData(user=self.user, email=False, mobile=False)
        pw = 'cmfad@fcnir35evs%'
        assert not self.user.check_password(pw)
        resp = self._set_password(pw, otp=otp)
        assert resp.json()['status'] == 'failed', resp.json()
        assert resp.json()['code'] == 'InvalidOTP'
        self.user.refresh_from_db()
        assert not self.user.check_password(pw)
        assert self.user.can_social_login_user_set_password
