import copy
import datetime
import json
from unittest.mock import MagicMock, Mock, patch

import requests
import responses
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.test.utils import modify_settings
from google.auth.transport import requests as grequests
from google.oauth2 import id_token
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from exchange.accounts.fetch_google_oauth2_certs import GOOGLE_OAUTH2_CERTS_CACHE_KEY
from exchange.accounts.models import PasswordRecovery, User, UserSms
from exchange.accounts.userprofile import UserProfileManager
from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from exchange.security.functions import get_emergency_cancel_url
from exchange.security.models import EmergencyCancelCode, LoginAttempt
from tests.base.utils import check_nobitex_response, mock_on_commit


class AuthenticationTest(APITestCase):
    def setUp(self) -> None:
        Settings.set("email_register", 'yes')

    @patch('exchange.security.signals.EmailManager.send_email')
    def test_authentication(self, send_email):
        """ Test authentication process including registration, login and logout
        """
        # registration
        registration_response = self.client.post('/auth/registration/', {
            'email': 'test@nobitex.com',
            'username': 'test@nobitex.com',
            'password1': 'P@Sw0rd123456789',
            'password2': 'P@Sw0rd123456789',
        })
        self.assertEqual(registration_response.status_code, status.HTTP_201_CREATED)
        assert registration_response.json()['expiresIn'] == 14400

        # check status register
        assert 'status' in registration_response.json() and registration_response.json()['status'] == 'ok'

        # check device field exist in response
        assert 'device' in registration_response.json() and registration_response.json()['device'] is not None

        # check LoginAttempt is created
        attempts = LoginAttempt.objects.filter(user__username='test@nobitex.com',
                                               device__device_id=registration_response.json()['device'])
        assert attempts.count() > 0
        assert attempts.first().is_successful

        # non authenticated token check
        authentication_response = self.client.post('/check/token')
        self.assertEqual(authentication_response.status_code, status.HTTP_200_OK)
        self.assertEqual(authentication_response.json()['status'], 'missing')

        # wrong authenticated token check
        self.client.credentials(HTTP_AUTHORIZATION=f'Token WRONG')
        authentication_response = self.client.post('/check/token')
        self.assertEqual(authentication_response.status_code, status.HTTP_200_OK)
        self.assertEqual(authentication_response.json()['status'], 'invalid')

        # registration authenticated token check
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {registration_response.json()["key"]}')
        authentication_response = self.client.post('/check/token')
        self.assertEqual(authentication_response.status_code, status.HTTP_200_OK)
        self.assertEqual(authentication_response.json()['status'], 'ok')
        self.client.credentials()

        # login
        login_response = self.client.post('/auth/login/', {
            'username': 'test@nobitex.com',
            'password': 'P@Sw0rd123456789',
            'remember': 'yes',
        })
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertEqual(login_response.json()['status'], 'success')
        self.assertEqual(login_response.json()['expiresIn'], 2592000)
        token = login_response.json()["key"]

        # login with mobile
        user = User.objects.get(username='test@nobitex.com')
        user.mobile = '09366946395'
        user.save(update_fields=['mobile'])
        Settings.set('mobile_login', 'yes')
        login_response = self.client.post('/auth/login/', {
            'username': '09366946395',
            'password': 'P@Sw0rd123456789',
            'remember': 'yes',
        })
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertEqual(login_response.json()['status'], 'success')
        token = login_response.json()["key"]

        # login authenticated token check
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        authentication_response = self.client.post('/check/token')
        self.assertEqual(authentication_response.status_code, status.HTTP_200_OK)
        self.assertEqual(authentication_response.json()['status'], 'ok')

        logout_response = self.client.post('/auth/logout/')
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)
        assert logout_response.json()['detail'] in [
            'Successfully logged out.',
            'خروج با موفقیت انجام شد.',
        ]

        # logged out token check
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        authentication_response = self.client.post('/check/token')
        self.assertEqual(authentication_response.status_code, status.HTTP_200_OK)
        self.assertEqual(authentication_response.json()['status'], 'invalid')

    @patch('exchange.security.signals.EmailManager.send_email')
    def test_auth_failure(self, send_email):
        user = User.objects.create_user(username='test@nobitex.com', email='test@nobitex.com', password='P@Sw0rd123456789')
        # login
        self.client.post('/auth/login/', {
            'username': 'test@nobitex.com',
            'password': 'P@Sw0rd123456789',
            'remember': 'yes',
        })
        # Ensure the user is set for first login
        self.assertEqual(user.login_attempts.count(), 1)

        # login failure for existing user
        login_response = self.client.post('/auth/login/', {
            'username': 'test@nobitex.com',
            'password': 'wrong',
            'remember': 'yes',
        })
        self.assertEqual(login_response.status_code, status.HTTP_403_FORBIDDEN)
        # Ensure the user is set for second login
        self.assertEqual(user.login_attempts.count(), 2)

        # login failure for non-existing user
        login_response = self.client.post('/auth/login/', {
            'username': 'wrong@wrong.com',
            'password': 'wrong',
            'remember': 'yes',
        })
        self.assertEqual(login_response.status_code, status.HTTP_403_FORBIDDEN)
        # Ensure attempt is recorded.
        self.assertTrue(LoginAttempt.objects.filter(username='wrong@wrong.com').exists())

    @staticmethod
    def get_main_server_verify_wrong_password_response_mock():
        response_mock = MagicMock()
        response_mock.json.return_value = {
            'status': 'failed',
            'message': 'Invalid username or password.'
        }
        return response_mock

    def test_authentication_fail_with_email_kyc2(self):
        """ Test authentication process including registration, login and logout
        """
        Settings.set("email_register", 'no')
        # registration
        registration_response = self.client.post('/auth/registration/', {
            'email': 'test@nobitex.com',
            'username': 'test@nobitex.com',
            'password1': 'P@Sw0rd123456789',
            'password2': 'P@Sw0rd123456789',
        })
        self.assertEqual(registration_response.status_code, status.HTTP_418_IM_A_TEAPOT)

        # check status register
        check_nobitex_response(registration_response.json(),
                               'failed',
                               'EmailRegistrationDisabled',
                               'Email registration is disabled')

    def test_registration_no_session_creation(self):
        sessions_count_before_registration = Session.objects.count()
        # registration
        registration_response = self.client.post(
            '/auth/registration/',
            {
                'email': 'test@nobitex.com',
                'username': 'test@nobitex.com',
                'password1': 'P@Sw0rd123456789',
                'password2': 'P@Sw0rd123456789',
            },
        )
        assert registration_response.status_code == status.HTTP_201_CREATED
        sessions_count_after_registration = Session.objects.count()
        assert sessions_count_before_registration == sessions_count_after_registration == 0

    @modify_settings(MIDDLEWARE={'remove': 'exchange.base.middlewares.DisableSessionForAPIsMiddleware'})
    def test_registration_session_creation_without_middleware(self):
        sessions_count_before_registration = Session.objects.count()
        # registration
        registration_response = self.client.post(
            '/auth/registration/',
            {
                'email': 'test@nobitex.com',
                'username': 'test@nobitex.com',
                'password1': 'P@Sw0rd123456789',
                'password2': 'P@Sw0rd123456789',
            },
        )
        assert registration_response.status_code == status.HTTP_201_CREATED
        sessions_count_after_registration = Session.objects.count()
        assert sessions_count_before_registration == 0
        assert sessions_count_after_registration == 1


class MobileRegisteredUserTest(APITestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_mobile = '0936946395'
        self.user_email = 'testUser@gmail.com'
        self.user_password = 'userP@ssw0rld'

    def test_authentication(self):
        """ Test authentication process including registration, login and logout
        """
        # registration
        registration_response = self.client.post('/auth/registration/', {
            'mobile': self.user_mobile,
            'username': self.user_mobile,
            'password1': self.user_password,
            'password2': self.user_password,
        })

        self.assertEqual(registration_response.status_code, status.HTTP_400_BAD_REQUEST)

        Settings.set('mobile_register', 'yes')
        registration_request = {
            'mobile': self.user_mobile,
            'username': self.user_mobile,
            'password1': self.user_password,
            'password2': self.user_password,
        }
        registration_response = self.client.post(
            '/auth/registration/',
            registration_request,
        ).json()
        assert registration_response['status'] == 'failed'
        assert registration_response['code'] == 'IncompleteRegisterError'
        assert registration_response['message'] == 'کد تایید را ارسال کنید.'

        assert not UserSms.objects.filter(to=self.user_mobile).exists()
        response = self.client.post(
            '/otp/request-public',
            {'mobile': self.user_mobile, 'usage': 'welcome_sms'},
        ).json()
        assert response['status'] == 'ok'

        mobile_otp = UserSms.objects.filter(to=self.user_mobile).order_by('-created_at').first().text
        registration_request['otp'] = mobile_otp
        registration_response = self.client.post(
            '/auth/registration/',
            registration_request,
             HTTP_USER_AGENT='Mozilla/5.0',
        )

        self.assertEqual(registration_response.status_code, status.HTTP_201_CREATED)
        registered_user = registration_response.json()
        assert registered_user['expiresIn'] == 14400

        # Check channel
        user = User.objects.get(username=self.user_mobile)
        assert UserProfileManager.get_user_property(user, 'regCh') == 'w'

        # non authenticated token check
        authentication_response = self.client.post('/check/token')
        self.assertEqual(authentication_response.status_code, status.HTTP_200_OK)
        self.assertEqual(authentication_response.json()['status'], 'missing')

        # wrong authenticated token check
        self.client.credentials(HTTP_AUTHORIZATION='Token WRONG')
        authentication_response = self.client.post('/check/token')
        self.assertEqual(authentication_response.status_code, status.HTTP_200_OK)
        self.assertEqual(authentication_response.json()['status'], 'invalid')

        # registration authenticated token check
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {registered_user["key"]}')
        authentication_response = self.client.post('/check/token')
        self.assertEqual(authentication_response.status_code, status.HTTP_200_OK)
        self.assertEqual(authentication_response.json()['status'], 'ok')
        self.client.credentials()

        Settings.set('mobile_login', 'yes')
        # login
        login_response = self.client.post('/auth/login/', {
            'username': self.user_mobile,
            'password': self.user_password,
            'remember': 'yes',
        })
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertEqual(login_response.json()['status'], 'success')
        token = login_response.json()["key"]

        # login with email
        user = User.objects.get(username=self.user_mobile)
        user.email = self.user_email
        user.save(update_fields=['email'])
        login_response = self.client.post('/auth/login/', {
            'username': self.user_email,
            'password': self.user_password,
            'remember': 'yes',
        })
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertEqual(login_response.json()['status'], 'success')
        token = login_response.json()["key"]

        # login authenticated token check
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        authentication_response = self.client.post('/check/token')
        self.assertEqual(authentication_response.status_code, status.HTTP_200_OK)
        self.assertEqual(authentication_response.json()['status'], 'ok')

        logout_response = self.client.post('/auth/logout/')
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)
        assert logout_response.json()['detail'] in [
            'Successfully logged out.',
            'خروج با موفقیت انجام شد.',
        ]

        # logged out token check
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        authentication_response = self.client.post('/check/token')
        self.assertEqual(authentication_response.status_code, status.HTTP_200_OK)
        self.assertEqual(authentication_response.json()['status'], 'invalid')


@patch('exchange.accounts.views.auth.validate_request_captcha', lambda request, **kwargs: True)
class ForgetPasswordTest(APITestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.forget_password_url = '/auth/forget-password/'
        self.forget_password_commit_url = 'auth/forget-password-commit/'
        self.username = 'ne1therEm@ilNorM0bile'
        self.user_mobile = '0936946395'
        self.user_email = 'forgetpasswordtestuser@gmail.com'
        self.user_password = 'userP@ssw0rld'
        self.user_changed_password = 'userChangedP@ssw0rld'
        self.forget_password_url = '/auth/forget-password/'
        self.forget_password_commit_url = '/auth/forget-password-commit/'
        self.sent_recovery_token = None

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username=self.username,
            password='!',
            email=self.user_email,
            mobile=self.user_mobile,
        )
        self.user.username = self.username
        self.user.set_password(self.user_password)
        self.user.save()
        Settings.set('mobile_forget_password', 'yes')

    def _check_password(self, password):
        self.user.refresh_from_db()
        return self.user.check_password(password)

    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_forget_password_with_email(self, mock_send_email: Mock):
        def check_email(*args, **kwargs):
            assert args[0] == self.user_email
            assert args[1] == 'reset_password'
            recovery = PasswordRecovery.objects.filter(
                user=self.user,
                status=PasswordRecovery.STATUS.new,
            ).first()
            self.sent_recovery_token = recovery.token.hex
            assert kwargs['data']['token'] == self.sent_recovery_token

        def check_notif_email(*args, **kwargs):
            assert args[0] == self.user_email
            assert args[1] == 'change_password_notif'
            assert kwargs['data']['emergency_cancel_url'] == get_emergency_cancel_url(self.user)

        mock_send_email.side_effect = check_email
        response = self.client.post(self.forget_password_url, data={
            'email': self.user_email,
        }).json()
        assert self._check_password(self.user_password)
        assert PasswordRecovery.objects.filter(
            user=self.user,
            token=self.sent_recovery_token,
        ).first().status == PasswordRecovery.STATUS.new

        mock_send_email.side_effect = check_notif_email
        self.cancel_code_obj, _ = EmergencyCancelCode.objects.get_or_create(
            user=self.user,
            defaults={
                'cancel_code': EmergencyCancelCode.make_unique_cancel_code,
            },
        )
        response = self.client.post(self.forget_password_commit_url, data={
            'email': self.user_email,
            'token': self.sent_recovery_token,
            'password1': self.user_changed_password,
            'password2': self.user_changed_password,
        }).json()
        assert response['status'] == 'ok'
        assert PasswordRecovery.objects.filter(
            user=self.user,
            token=self.sent_recovery_token,
        ).first().status == PasswordRecovery.STATUS.confirmed
        assert self._check_password(self.user_changed_password)

    @patch('exchange.accounts.models.UserSms.objects.create')
    def test_forget_password_with_mobile(self, mock_send_sms: Mock):
        assert self.user.check_password(self.user_password)
        def check_sms(*args, **kwargs):
            assert kwargs['user'] == self.user
            assert kwargs['tp'] == UserSms.TYPES.verify_password_recovery
            assert kwargs['to'] == self.user.mobile
            assert kwargs['template'] == UserSms.TEMPLATES.password_recovery
            recovery = PasswordRecovery.objects.filter(
                user=self.user,
                status=PasswordRecovery.STATUS.new,
            ).first()
            self.sent_recovery_token = recovery.otp
            assert kwargs['text'] == self.sent_recovery_token

        mock_send_sms.side_effect = check_sms
        response = self.client.post(self.forget_password_url, data={
            'mobile': self.user_mobile,
        }).json()
        assert self._check_password(self.user_password)
        assert PasswordRecovery.objects.filter(
            user=self.user,
            otp=self.sent_recovery_token,
        ).first().status == PasswordRecovery.STATUS.new
        response = self.client.post(self.forget_password_commit_url, data={
            'mobile': self.user_mobile,
            'token': self.sent_recovery_token,
            'password1': self.user_changed_password,
            'password2': self.user_changed_password,
        }).json()
        assert response['status'] == 'ok'
        assert PasswordRecovery.objects.filter(
            user=self.user,
            otp=self.sent_recovery_token,
        ).first().status == PasswordRecovery.STATUS.confirmed
        assert self._check_password(self.user_changed_password)

    def test_multiple_forget_password_calls(self):
        assert self.user.recovery_records.count() == 0
        response = self.client.post(self.forget_password_url, data={
            'mobile': self.user_mobile,
        }).json()
        assert response['status'] == 'ok'
        assert self.user.recovery_records.count() == 1
        response = self.client.post(self.forget_password_url, data={
            'email': self.user_email,
        }).json()
        assert response['status'] == 'ok'
        assert self.user.recovery_records.count() == 1

    def test_invalid_usernames(self):
        response = self.client.post(self.forget_password_url, data={
            'email': 'testuser@gmail.com',
        }).json()
        assert response['status'] == 'ok'  # cuz of security issues it returns ok, but actually it's 'failed'
        response = self.client.post(self.forget_password_url, data={
            'mobile': '989122233444',
        }).json()
        assert response['status'] == 'ok'

    @patch('exchange.accounts.models.ir_now')
    def test_expiration(self, patched_ir_now):
        assert self.user.recovery_records.first() is None
        patched_ir_now.return_value = ir_now()
        response = self.client.post(self.forget_password_url, data={
            'email': self.user_email,
        }).json()
        assert response['status'] == 'ok'
        recovery = self.user.recovery_records.first()
        assert recovery.pk
        assert recovery.status == PasswordRecovery.STATUS.new
        patched_ir_now.return_value = ir_now() + datetime.timedelta(minutes=10)
        response = self.client.post(self.forget_password_url, data={
            'email': self.user_email,
        }).json()
        recovery.refresh_from_db()
        assert recovery.status == PasswordRecovery.STATUS.expired
        assert self.user.recovery_records.count() == 2
        assert self.client.post(self.forget_password_commit_url, data={
            'email': self.user_email,
            'token': recovery.token.hex,
            'password1': self.user_changed_password,
            'password2': self.user_changed_password,
        }).json()['status'] == 'failed'
        recovery = self.user.recovery_records.order_by('created_at').last()
        assert self.client.post(self.forget_password_commit_url, data={
            'email': self.user_email,
            'token': recovery.token.hex,
            'password1': self.user_changed_password,
            'password2': self.user_changed_password,
        }).json()['status'] == 'ok'

    def test_password_validation(self):
        self.client.post(self.forget_password_url, data={
            'email': self.user_email,
        })
        token = self.user.recovery_records.first().token.hex
        for password1, password2 in [
            ('lsakdfnk@!#g2l3g23g', 'Qsakdfnk@!#g2l3g23g',),
            ('Ax@123', 'Ax@123',),
            ('123123123123', '123123123123',),
            (self.user_email, self.user_email,),
            (self.user_mobile, self.user_mobile,),
            (self.username, self.username,),
        ]:
            assert self.client.post(self.forget_password_commit_url, data={
                'email': self.user_email,
                'token': token,
                'password1': password1,
                'password2': password2,
            }).json()['status'] == 'failed'

    def test_invalid_token(self):
        self.client.post(self.forget_password_url, data={
            'email': self.user_email,
        })
        token = self.user.recovery_records.first().token.hex
        token = ('2' if token[0] == '1' else '1') + token[1:]
        assert self.client.post(self.forget_password_commit_url, data={
            'email': self.user_email,
            'token': token,
            'password1': self.user_changed_password,
            'password2': self.user_changed_password,
        }).json()['status'] == 'failed'
        token = token[1:]
        assert self.client.post(self.forget_password_commit_url, data={
            'email': self.user_email,
            'token': token,
            'password1': self.user_changed_password,
            'password2': self.user_changed_password,
        }).json()['status'] == 'failed'

    def test_invalid_otp(self):
        self.client.post(self.forget_password_url, data={
            'mobile': self.user_mobile,
        })
        otp = self.user.recovery_records.first().otp
        otp = ('2' if otp[0] == '1' else '1') + otp[1:]
        assert self.client.post(self.forget_password_commit_url, data={
            'mobile': self.user_mobile,
            'token': otp,
            'password1': self.user_changed_password,
            'password2': self.user_changed_password,
        }).json()['status'] == 'failed'

    def test_required_fields(self):
        assert (
            self.client.post(self.forget_password_url, data={}).json()['status'] == 'ok'
        )  # cuz of security issues it returns ok, but actually it's 'failed'
        assert self.client.post(self.forget_password_url, data={'email': self.user_email}).json()['status'] == 'ok'
        recovery = self.user.recovery_records.first()
        for request_body, error in [
            ({
                'token': recovery.otp,
                'password1': self.user_changed_password,
                'password2': self.user_changed_password,
            },['اطلاعات کامل وارد نشده']),
            ({
                'token': recovery.token.hex,
                'password1': self.user_changed_password,
                'password2': self.user_changed_password,
            },['اطلاعات کامل وارد نشده']),
            ({
                'email': self.user_email,
                'token': recovery.otp,
                'password1': self.user_changed_password,
                'password2': self.user_changed_password,
            },'توکن وارد شده نامعتبر است.'),
            ({
                'mobile': self.user_mobile,
                'token': recovery.token.hex,
                'password1': self.user_changed_password,
                'password2': self.user_changed_password,
            },'توکن وارد شده نامعتبر است.'),
            ({
                'email': self.user_email,
                'password1': self.user_changed_password,
                'password2': self.user_changed_password,
            },['اطلاعات کامل وارد نشده']),
            ({
                'mobile': self.user_mobile,
                'token': recovery.otp,
                'password1': self.user_changed_password,
            },['گذرواژه و تکرار آن را به درستی وارد نمایید.']),
            ({
                'mobile': self.user_mobile,
                'token': recovery.otp,
                'password2': self.user_changed_password,
            },['گذرواژه و تکرار آن را به درستی وارد نمایید.']),
            ({
                'email': self.user_email,
                'token': recovery.token.hex,
                'password1': self.user_changed_password,
            },['گذرواژه و تکرار آن را به درستی وارد نمایید.']),
            ({
                'email': self.user_email,
                'token': recovery.token.hex,
                'password1': self.user_changed_password,
            },['گذرواژه و تکرار آن را به درستی وارد نمایید.']),
        ]:
            response = self.client.post(
                self.forget_password_commit_url, data=request_body
            ).json()
            assert response['status'] == 'failed'
            error_key = 'non_field_errors' if isinstance(error, list) else 'message'
            assert response[error_key] == error

    def _check_token(self):
        try:
            return self.user.auth_token.key == self.token_key
        except:
            return False

    @patch('exchange.accounts.models.UserSms.objects.create')
    def test_logout_after_change_password(self, mock_send_sms: Mock):
        def mock_send_sms_side_effect(*args, **kwargs):
            recovery = PasswordRecovery.objects.filter(
                user=self.user,
                status=PasswordRecovery.STATUS.new,
            ).first()
            self.sent_recovery_token = recovery.otp

        mock_send_sms.side_effect = mock_send_sms_side_effect
        self.token_key = 'token_key'
        Token.objects.create(user=self.user, key=self.token_key)
        assert self._check_token()
        self.client.post(self.forget_password_url, data={
            'mobile': self.user_mobile,
        })
        assert self._check_token()
        response = self.client.post(self.forget_password_commit_url, data={
            'mobile': self.user_mobile,
            'token': self.sent_recovery_token,
            'password1': self.user_changed_password,
            'password2': self.user_changed_password,
        }).json()
        assert response['status'] == 'ok'
        assert self._check_password(self.user_changed_password)
        assert not self._check_token()

    def test_mobile_forget_password_settings(self):
        Settings.set('mobile_forget_password', 'no')
        response = self.client.post(self.forget_password_url, data={
            'mobile': self.user_mobile,
        }).json()
        assert response['status'] == 'failed'


@patch('exchange.accounts.views.auth.validate_request_captcha', lambda request, **kwargs: True)
@patch('django.db.transaction.on_commit', lambda t: t())
class ChangePasswordNotificationTest(APITestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.forget_password_url = '/auth/forget-password/'
        self.forget_password_commit_url = '/auth/forget-password-commit/'
        self.change_password_url = '/auth/user/change-password'

        self.username = 'ne1therEm@ilNorM0bile'
        self.user_mobile = '0936946395'
        self.user_email = 'forgetpasswordtestuser@gmail.com'
        self.user_password = 'userOld@ssw0rld'
        self.user_new_password = 'userNewP@ssw0rld'

    def setUp(self) -> None:
        self.user: User = User.objects.create_user(
            username=self.username,
            password='!',
            email=self.user_email,
            mobile=self.user_mobile,
        )
        self.user.username = self.username
        self.user.set_password(self.user_password)
        self.user.save()

        verification_profile = self.user.get_verification_profile()
        verification_profile.email_confirmed = True
        verification_profile.mobile_confirmed = True
        verification_profile.save(update_fields=['email_confirmed', 'mobile_confirmed'])

        self.user_client = copy.deepcopy(self.client)
        auth_token = 'token'
        Token.objects.create(user=self.user, key=auth_token)
        self.user_client.credentials(HTTP_AUTHORIZATION=f'Token {auth_token}')
        self.anonymous_client = self.client

        Settings.set('mobile_forget_password', 'yes')

    def _check_password(self, password):
        self.user.refresh_from_db()
        assert self.user.check_password(password)

    def _assert_mobile_notif_side_effect(self, *args, **kwargs):
        assert kwargs['user'].pk == self.user.pk
        assert kwargs['tp'] == UserSms.TYPES.change_password_notif

    def _assert_email_notif_side_effect(self, *args, **kwargs):
        assert args[0] == self.user_email
        assert args[1] == 'change_password_notif'

    def _remove_user_email(self):
        self.user.email = self.user.mobile + '@mobile.ntx.ir'
        self.user.save()
        verification_profile = self.user.get_verification_profile()
        verification_profile.email_confirmed = False
        verification_profile.save(update_fields=['email_confirmed'])

    def _remove_user_mobile(self):
        self.user.mobile = ''
        self.user.save()
        verification_profile = self.user.get_verification_profile()
        verification_profile.mobile_confirmed = False
        verification_profile.save(update_fields=['mobile_confirmed'])

    def _call_change_password(self):
        response = self.user_client.post(self.change_password_url, data={
            'currentPassword': self.user_password,
            'newPassword': self.user_new_password,
            'newPasswordConfirm': self.user_new_password,
        }).json()
        assert response['status'] == 'ok'
        self._check_password(self.user_new_password)

    @patch('exchange.accounts.models.UserSms.objects.create')
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_user_with_no_email_and_no_mobile_confirmed_change_password(
        self,
        _,
        mock_send_email: Mock,
        mock_create_usersms: Mock,
    ):
        self._remove_user_email()
        self._remove_user_mobile()
        self._call_change_password()
        mock_send_email.assert_not_called()
        mock_create_usersms.assert_not_called()

    @patch('exchange.accounts.models.UserSms.objects.create')
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_user_with_no_email_change_password(self,
        mock_send_email: Mock,
        mock_create_usersms: Mock,
    ):
        self._remove_user_email()
        mock_create_usersms.side_effect = self._assert_mobile_notif_side_effect
        self._call_change_password()
        mock_send_email.assert_not_called()
        mock_create_usersms.assert_called()

    @patch('exchange.accounts.models.UserSms.objects.create')
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_user_with_no_mobile_change_password(self,
        mock_send_email: Mock,
        mock_create_usersms: Mock,
    ):
        self._remove_user_mobile()
        mock_send_email.side_effect = self._assert_email_notif_side_effect
        self._call_change_password()
        mock_create_usersms.assert_not_called()
        mock_send_email.assert_called()

    @patch('exchange.accounts.models.UserSms.objects.create')
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_user_with_mobile_and_email_change_password(self,
        mock_send_email: Mock,
        mock_create_usersms: Mock,
    ):
        mock_send_email.side_effect = self._assert_email_notif_side_effect
        self._call_change_password()
        mock_create_usersms.assert_not_called()
        mock_send_email.assert_called()

    @patch('exchange.accounts.models.UserSms.objects.create')
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_user_with_no_email_forget_password(self,
        mock_send_email: Mock,
        mock_create_usersms: Mock,
    ):
        self._remove_user_email()
        response = self.anonymous_client.post(self.forget_password_url, data={
            'mobile': self.user_mobile,
        }).json()
        assert response['status'] == 'ok'
        mock_create_usersms.side_effect = self._assert_mobile_notif_side_effect
        token = PasswordRecovery.objects.order_by('created_at').last().otp
        response = self.anonymous_client.post(self.forget_password_commit_url, data={
            'mobile': self.user_mobile,
            'token': token,
            'password1': self.user_new_password,
            'password2': self.user_new_password,
        }).json()
        assert response['status'] == 'ok'
        self._check_password(self.user_new_password)
        mock_send_email.assert_not_called()

    @patch('exchange.accounts.models.UserSms.objects.create')
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_user_with_no_mobile_forget_password(self,
        mock_send_email: Mock,
        mock_create_usersms: Mock,
    ):
        self._remove_user_mobile()
        response = self.anonymous_client.post(self.forget_password_url, data={
            'email': self.user_email,
        }).json()
        assert response['status'] == 'ok'
        mock_send_email.side_effect = self._assert_email_notif_side_effect
        token = PasswordRecovery.objects.order_by('created_at').last().token
        response = self.anonymous_client.post(self.forget_password_commit_url, data={
            'email': self.user_email,
            'token': token,
            'password1': self.user_new_password,
            'password2': self.user_new_password,
        }).json()
        assert response['status'] == 'ok'
        self._check_password(self.user_new_password)
        mock_create_usersms.assert_not_called()

    @patch('exchange.accounts.models.UserSms.objects.create')
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_user_with_mobile_and_email_forget_password(self,
        mock_send_email: Mock,
        mock_create_usersms: Mock,
    ):
        response = self.anonymous_client.post(self.forget_password_url, data={
            'email': self.user_email,
        }).json()
        assert response['status'] == 'ok'
        mock_send_email.side_effect = self._assert_email_notif_side_effect
        token = PasswordRecovery.objects.order_by('created_at').last().token
        response = self.anonymous_client.post(self.forget_password_commit_url, data={
            'email': self.user_email,
            'token': token,
            'password1': self.user_new_password,
            'password2': self.user_new_password,
        }).json()
        assert response['status'] == 'ok'
        self._check_password(self.user_new_password)
        mock_create_usersms.assert_not_called()


class TestGoogleSocialLogin(APITestCase):

    @patch('google.oauth2.id_token.verify_oauth2_token')
    def test_google_social_login_success(self, mock_verify_token):
        email = 'sample@gmail.com'
        request_data = {
            'token': 'valid-token',
            'device': 'MaN4spkr',
            'remember': 'yes',
        }
        id_token_payload = {
            'aud': '1039155241638-5ehvg8etjmdo2i6v7h8553m3hak0n7sp.apps.googleusercontent.com',
            'azp': '1039155241638-5ehvg8etjmdo2i6v7h8553m3hak0n7sp.apps.googleusercontent.com',
            'email': email,
            'email_verified': True,
            'exp': 1741428500,
            'family_name': 'alavi',
            'given_name': 'ali',
            'iat': 1741424900,
            'iss': 'https://accounts.google.com',
            'jti': '7c249fe2aca751b4b30ee0c57e5b234bc13603b3',
            'name': 'ali alavi',
            'nbf': 1741424600,
            'picture': 'https://lh3.googleusercontent.com/a/ACg8ocJglw5mL8oKjO7KVRk1HTi7iweYHbqP_UPymL5rZKB9drwQKQ=s96-c',
            'sub': '114386838446789955832',
        }
        mock_verify_token.return_value = id_token_payload

        # when->
        response = self.client.post(
            '/auth/google/', data=json.dumps(request_data, indent=4), content_type='application/json'
        ).json()

        assert response['status'] == 'ok'
        assert response['key'] is not None
        assert response['device'] is not None

        registered_user = User.objects.filter(email=email).first()
        assert registered_user is not None
        assert registered_user.is_email_verified == True

    def test_fetch_certs_using_cache(self):
        expected_certs = {'test': 'test'}
        cache.set(GOOGLE_OAUTH2_CERTS_CACHE_KEY, expected_certs)

        session = requests.Session()
        certs = id_token._fetch_certs(grequests.Request(session=session), id_token._GOOGLE_OAUTH2_CERTS_URL)

        assert certs == expected_certs

    @responses.activate
    def test_fetch_certs_set_cache(self):
        expected_certs = {'test': 'test'}

        responses.get(
            url=id_token._GOOGLE_OAUTH2_CERTS_URL,
            json=expected_certs,
            status=200,
        )

        session = requests.Session()
        certs = id_token._fetch_certs(grequests.Request(session=session), id_token._GOOGLE_OAUTH2_CERTS_URL)

        assert certs == expected_certs
        assert cache.get(GOOGLE_OAUTH2_CERTS_CACHE_KEY) == expected_certs
