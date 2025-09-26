import datetime
from unittest.mock import MagicMock, patch

import pytest
import responses
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.timezone import now

from exchange.accounts.captcha import ARCaptcha, CaptchaHandler, UnacceptableCaptchaTypeError
from exchange.accounts.models import UserSms
from exchange.accounts.views.auth import validate_request_captcha
from exchange.base.models import Settings
from exchange.captcha.models import CaptchaStore
from tests.base.utils import NobitexRequestFactory


class TestCaptcha(TestCase):

    def setUp(self):
        self.factory = NobitexRequestFactory()
        cache.set('settings_login_captcha_types', CaptchaHandler.get_all_types())

    @override_settings(CAPTCHA_PICK_DEFAULT_METHOD='random_order')
    def test_get_captcha_key_view_fallback(self):
        # Pool is empty
        r = self.client.post('/captcha/get-captcha-key')
        assert r.status_code == 200
        r = r.json()
        assert r['status'] == 'ok'
        assert r['captcha']
        assert r['captcha']['key']
        assert r['captcha']['image_url']

    @override_settings(CAPTCHA_PICK_DEFAULT_METHOD='random_order')
    def test_get_captcha_key_view_random_order_method(self):
        call_command('captcha_create_pool', pool_size=10, loop=False)

        r = self.client.post('/captcha/get-captcha-key')
        assert r.status_code == 200
        r = r.json()
        assert r['status'] == 'ok'
        assert r['captcha']
        assert r['captcha']['key']
        assert r['captcha']['image_url']

    @override_settings(CAPTCHA_PICK_DEFAULT_METHOD='tablesample', CAPTCHA_PICK_SAMPLE_RATE=100)
    def test_get_captcha_key_view_tablesample_method(self):
        call_command('captcha_create_pool', pool_size=10, loop=False)
        r = self.client.post('/captcha/get-captcha-key')
        assert r.status_code == 200
        r = r.json()
        assert r['status'] == 'ok'
        assert r['captcha']
        assert r['captcha']['key']
        assert r['captcha']['image_url']

    def test_captcha_select_view(self):
        # Generic request
        r = self.client.post('/captcha/select')
        assert r.status_code == 200
        r = r.json()
        assert r['status'] == 'ok'
        assert r['acceptableTypes'] == list(CaptchaHandler.MAPPING.keys())
        # IR request
        r = self.client.post('/captcha/select', HTTP_CF_IPCOUNTRY='IR')
        assert r.status_code == 200
        r = r.json()
        assert r['status'] == 'ok'
        assert r['acceptableTypes'] == list(CaptchaHandler.MAPPING.keys())

        r = self.client.post('/captcha/select', data=dict(usage='login'), HTTP_CF_IPCOUNTRY='IR')
        assert r.status_code == 200
        r = r.json()
        assert r['status'] == 'ok'
        assert r['acceptableTypes'] == ['django-captcha', 'arcaptcha', 'recaptcha', 'hcaptcha']

        r = self.client.post('/captcha/select', data=dict(usage='login'), HTTP_CF_IPCOUNTRY='CA')
        assert r.status_code == 200
        r = r.json()
        assert r['status'] == 'ok'
        assert r['acceptableTypes'] == ['arcaptcha', 'recaptcha', 'hcaptcha']

        for usage in ['forget-password', 'forget-password-commit']:
            for country in ['IR', 'CA']:
                r = self.client.post('/captcha/select', data=dict(usage=usage), HTTP_CF_IPCOUNTRY=country)
                assert r.status_code == 200
                r = r.json()
                assert r['status'] == 'ok'
                assert r['acceptableTypes'] == ['arcaptcha', 'recaptcha', 'hcaptcha']

    @override_settings(DISABLE_RECAPTCHA=False)
    def test_validate_request_captcha(self):
        Settings.set_cached_json(
            'captcha_usage_configs_v2',
            {
                'NON_IR': {
                    'default': {'route': '', 'types': ['django-captcha', 'arcaptcha', 'recaptcha', 'hcaptcha']},
                    'login': {
                        'route': 'auth/login/',
                        'types': ['arcaptcha', 'recaptcha', 'hcaptcha'],
                    },
                },
                'IR': {
                    'default': {'route': '', 'types': ['django-captcha', 'arcaptcha', 'recaptcha', 'hcaptcha']},
                    'login': {
                        'route': 'auth/login/',
                        'types': ['django-captcha', 'arcaptcha', 'recaptcha', 'hcaptcha'],
                    },
                },
            },
        )
        # Captcha type check
        request = self.factory.post(
            '/auth/login/',
            {
                'user': 'a',
                'password': 'b',
                'captchaType': 'django-captcha',
                'captcha': 'XXXXX',
            },
            HTTP_CF_IPCOUNTRY='CA',
        )
        with pytest.raises(UnacceptableCaptchaTypeError):
            validate_request_captcha(request, check_type=True)

        request = self.factory.post(
            '/auth/login/',
            {
                'user': 'a',
                'password': 'b',
                'captchaType': 'django-captcha',
                'captcha': 'XXXXX',
            },
            HTTP_CF_IPCOUNTRY='IR',
        )
        validate_request_captcha(request, check_type=True)

    @override_settings(DISABLE_RECAPTCHA=False)
    def test_django_captcha_without_usage(self):
        # Non-existing captcha key
        cache.set('settings_login_captcha_types', ['django-captcha'])
        Settings.set_cached_json(
            'captcha_usage_configs_v2',
            {
                'NON_IR': {
                    'default': {'route': '', 'types': ['django-captcha', 'arcaptcha', 'recaptcha', 'hcaptcha']},
                    'login': {
                        'route': 'auth/login/',
                        'types': ['django-captcha', 'arcaptcha', 'recaptcha', 'hcaptcha'],
                    },
                }
            },
        )
        request = self.factory.post(
            '/auth/login/',
            {
                'user': 'a',
                'password': 'b',
                'captchaType': 'django-captcha',
                'captcha': 'FDFIOX',
                'key': 'testcaptcha1',
            },
        )
        # Incorrect captcha value
        assert not validate_request_captcha(request, check_type=True)
        CaptchaStore.objects.create(
            challenge='FDEIOX', response='FDEIOX', hashkey='testcaptcha1',
            expiration=now() + datetime.timedelta(minutes=1),
        )
        assert not validate_request_captcha(request, check_type=True)
        # Correct captcha value
        request = self.factory.post('/auth/login/', {
            'user': 'a', 'password': 'b', 'captchaType': 'django-captcha', 'captcha': 'FDEIOX', 'key': 'testcaptcha1',
        })
        assert validate_request_captcha(request, check_type=True)

    @override_settings(DISABLE_RECAPTCHA=False, ARCAPTCHA_SITE_KEY='test_site_key', ARCAPTCHA_SECRET_KEY='test_secret_key')
    @responses.activate
    @patch('exchange.accounts.captcha.Settings.get_value')
    def test_arcaptcha(self, mock_settings_get_value):
        mock_base_url = 'https://mocked-url.example.com'
        mock_settings_get_value.return_value = mock_base_url
        responses.post(ARCaptcha.get_verify_url(), json={'success': True})

        request = self.factory.post('/auth/login/', {
            'user': 'a', 'password': 'b', 'captchaType': 'arcaptcha', 'captcha': 'FDEIOX',
        })
        assert validate_request_captcha(request, check_type=True)
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == f'{mock_base_url}/arcaptcha/api/verify'
        mock_settings_get_value.assert_any_call('captcha_arcaptcha_base_url', default='https://api.arcaptcha.ir')

    @override_settings(DISABLE_RECAPTCHA=False)
    @responses.activate
    def test_recaptcha(self):
        responses.post('https://www.google.com/recaptcha/api/siteverify', json={'success': True})
        request = self.factory.post('/auth/login/', {
            'user': 'a', 'password': 'b', 'captchaType': 'recaptcha', 'captcha': 'FDEIOX',
        })
        assert validate_request_captcha(request, check_type=True)

    @override_settings(DISABLE_RECAPTCHA=False)
    @responses.activate
    def test_recaptcha_android(self):
        responses.post('https://www.google.com/recaptcha/api/siteverify', json={'success': True})
        request = self.factory.post('/auth/login/', {
            'user': 'a', 'password': 'b', 'client': 'android', 'captcha': 'FDEIOX',
        })
        assert validate_request_captcha(request, check_type=True)

    @override_settings(DISABLE_RECAPTCHA=False)
    @responses.activate
    def test_hcaptcha(self):
        responses.post('https://hcaptcha.com/siteverify', json={'success': True})

        request = self.factory.post('/auth/login/', {
            'user': 'a', 'password': 'b', 'captchaType': 'hcaptcha', 'captcha': 'FDEIOX',
        })
        assert validate_request_captcha(request, check_type=True)


class TestCaptchaInLoginScenario(TestCase):

    def setUp(self):
        self.local_captcha_cache = dict()
        self.captcha_cache_key = 'test_captcha_key'

    @override_settings(DISABLE_RECAPTCHA=False)
    @patch('exchange.accounts.captcha.DjangoCaptcha.verify')
    def test_captcha_verification_by_cache_not_available_in_login_scenario(self, verify):
        verify.side_effect = True

        captcha_key = self.get_captcha_key()
        self.client.post(
            '/auth/login/',
            {'user': 'a', 'password': 'b', 'captcha': captcha_key, 'captchaType': 'django-captcha'},
            HTTP_CF_IPCOUNTRY='IR')
        verify.assert_called_once_with(using_cache=False)

    @override_settings(DISABLE_RECAPTCHA=False)
    @patch('exchange.accounts.captcha.BaseCaptcha.verify_by_cache', new_callable=MagicMock)
    @patch('exchange.accounts.captcha.BaseCaptcha.cache_captcha_validation', new_callable=MagicMock)
    def test_captcha_verification_by_cache_in_login_scenario(self, cache_captcha_validation, verify_by_cache):
        cache_captcha_validation.side_effect = self.cache_captcha_validation_mock
        verify_by_cache.side_effect = self.verify_by_cache_mock

        captcha_key = self.get_captcha_key()
        self.client.post(
            '/auth/login/',
            {'user': 'a', 'password': 'b', 'captcha': captcha_key, 'captchaType': 'django-captcha'},
            HTTP_CF_IPCOUNTRY='IR')
        assert cache_captcha_validation.call_count == 0
        assert verify_by_cache.call_count == 0

    def cache_captcha_validation_mock(self):
        self.local_captcha_cache[self.captcha_cache_key] = True

    def verify_by_cache_mock(self):
        return self.captcha_cache_key in self.local_captcha_cache

    def get_captcha_key(self):
        captcha_response = self.client.post('/captcha/get-captcha-key')
        return captcha_response.json().get('captcha').get('key')


class TestCaptchaInRegistrationScenario(TestCase):

    def setUp(self):
        cache.set('settings_login_captcha_types', CaptchaHandler.get_all_types())
        Settings.set('mobile_register', 'yes')
        self.local_captcha_cache = dict()
        self.captcha_cache_key = 'test_captcha_key'
        self.user_mobile = '09940782836'
        self.user_password = 'userP@ssw0rld'
        self.registration_request = {
            'mobile': self.user_mobile,
            'username': self.user_mobile,
            'password1': self.user_password,
            'password2': self.user_password,
        }
        self.otp_request = {
            'mobile': self.user_mobile,
            'usage': 'welcome_sms',
            'captchaType': 'django-captcha',
            'key': '',
            'captcha': ''
        }

    @override_settings(DISABLE_RECAPTCHA=False)
    @patch('exchange.accounts.captcha.DjangoCaptcha.verify')
    def test_captcha_verification_by_cache_available_in_registration_scenario(self, verify):
        verify.side_effect = True
        self.client.post('/auth/registration/', self.registration_request, HTTP_CF_IPCOUNTRY='IR')
        verify.assert_called_once_with(using_cache=True)

    @override_settings(DISABLE_RECAPTCHA=False)
    @patch('exchange.accounts.captcha.BaseCaptcha.verify_by_cache', new_callable=MagicMock)
    @patch('exchange.accounts.captcha.BaseCaptcha.cache_captcha_validation', new_callable=MagicMock)
    def test_captcha_verification_by_cache_in_registration_scenario(self, cache_captcha_validation, verify_by_cache):
        cache_captcha_validation.side_effect = self.cache_captcha_validation_mock
        verify_by_cache.side_effect = self.verify_by_cache_mock

        captcha_key = self.get_captcha_key()
        self.set_captcha_challenge(captcha_key)

        self.client.post('/otp/request-public', self.otp_request).json()

        mobile_otp = UserSms.objects.filter(to=self.user_mobile).order_by('-created_at').first().text
        self.registration_request['otp'] = mobile_otp
        self.client.post(
            '/auth/registration/',
            self.registration_request,
            HTTP_USER_AGENT='Mozilla/5.0',
            HTTP_CF_IPCOUNTRY='IR',
        )

        assert cache_captcha_validation.call_count == 1
        assert verify_by_cache.call_count == 2

    def cache_captcha_validation_mock(self):
        self.local_captcha_cache[self.captcha_cache_key] = True

    def verify_by_cache_mock(self):
        return self.captcha_cache_key in self.local_captcha_cache

    def get_captcha_key(self):
        captcha_response = self.client.post('/captcha/get-captcha-key')
        return captcha_response.json().get('captcha').get('key')

    def set_captcha_challenge(self, captcha_key):
        captcha_object = CaptchaStore.objects.filter(hashkey=captcha_key, expiration__gte=timezone.now()).first()
        captcha_challenge = captcha_object.challenge
        self.otp_request['key'] = captcha_key
        self.otp_request['captcha'] = captcha_challenge


@pytest.mark.parametrize(
    'url_path, usage',
    [
        ('auth/login/', 'login'),
        ('auth/registration/', 'registration'),
        ('auth/forget-password/', 'forget-password'),
        ('users/request-tfa-removal', 'request-tfa-removal'),
        ('users/confirm-tfa-removal/username', 'confirm-tfa-removal'),
        ('otp/request-public', 'otp-request-public'),
        ('gift/redeem', 'gift-redeem'),
        ('gift/redeem-lightning', 'gift-redeem-lightning'),
        ('marketing/suggestion/add', 'marketing-suggestion-add'),
    ],
)
def test_cal_usage_based_on_request_url(url_path, usage):
    captcha_handler = CaptchaHandler(
        country='test',
        check_type=False,
        ip='test',
        client='test',
        captcha_type='test',
        captcha_key='test',
        key='test',
        url_path=url_path,
    )
    assert captcha_handler.usage_based_on_url_path == usage
