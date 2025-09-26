from typing import ClassVar, List, Optional
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from exchange.accounts.constants import DEFAULT_CAPTCHA_USAGE_CONFIGS_V2
from exchange.base.logging import metric_incr, report_exception
from exchange.base.models import Settings
from exchange.base.normalizers import normalize_digits
from exchange.captcha.helpers import captcha_image_url, has_farsi_chars
from exchange.captcha.models import CaptchaStore, captcha_settings


class CaptchaError(ValueError):
    pass


class UnacceptableCaptchaTypeError(CaptchaError):
    def __init__(self, *args, acceptable_types=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.acceptable_types = acceptable_types or []


class CaptchaProviderError(CaptchaError):
    def __init__(self, provider: str):
        self.provider = provider

    def __str__(self):
        return f'{self.provider} captcha request failed'


class BaseCaptcha:

    def __init__(self, captcha_key: str, client: str, ip: str, key: str, extra_data: Optional[dict] = None):
        self.captcha_key = captcha_key
        self.extra_data = extra_data
        self.client = client
        self.key = key
        self.ip = ip

    @classmethod
    def get_verify_url(cls):
        raise NotImplementedError()

    def verify(self, using_cache=False) -> bool:
        raise NotImplementedError()

    def verify_by_cache(self) -> bool:
        cache_key = self._get_cache_key()
        if cache.get(cache_key):
            cache.delete(cache_key)
            return True
        return False

    def cache_captcha_validation(self):
        cache.set(key=self._get_cache_key(), value=1, timeout=captcha_settings.get_timeout() * 60)

    def _get_cache_key(self) -> str:
        mobile = self.extra_data.get('mobile', '') if self.extra_data else ''
        return f'{self.__class__.__name__}_{self.key}_{self.ip}_{mobile}'


class ReCaptcha(BaseCaptcha):
    @classmethod
    def get_verify_url(cls):
        return 'https://www.google.com/recaptcha/api/siteverify'

    def verify(self, using_cache=False) -> bool:
        if using_cache and self.verify_by_cache():
            return True
        if self.client in {'android', 'ios'}:
            secret = settings.ANDROID_RECAPTCHA_PRIVATE_KEY
        else:
            secret = settings.FRONT_RECAPTCHA_PRIVATE_KEY
        response = requests.post(
            self.get_verify_url(),
            data={
                'secret': secret,
                'response': self.captcha_key,
                'remoteip': self.ip,
            },
            timeout=30,
        )
        response.raise_for_status()
        if not response.json().get('success'):
            raise CaptchaProviderError(self.__class__.__name__)
        if using_cache:
            self.cache_captcha_validation()
        return True


class HCaptcha(BaseCaptcha):
    @classmethod
    def get_verify_url(cls):
        return 'https://hcaptcha.com/siteverify'

    def verify(self, using_cache=False) -> bool:
        if using_cache and self.verify_by_cache():
            return True
        response = requests.post(
            self.get_verify_url(),
            data={
                'secret': settings.HCAPTCHA_SECRET_KEY,
                'response': self.captcha_key,
                'remoteip': self.ip,
            },
            timeout=10,
        )
        response.raise_for_status()
        if not response.json().get('success'):
            raise CaptchaProviderError(self.__class__.__name__)
        if using_cache:
            self.cache_captcha_validation()
        return True


class ARCaptcha(BaseCaptcha):
    """
    Documentation available at:
    https://docs.arcaptcha.co/API/Verify
    """

    @classmethod
    def get_verify_url(cls):
        base_url = Settings.get_value('captcha_arcaptcha_base_url', default='https://api.arcaptcha.ir')
        return urljoin(base_url, 'arcaptcha/api/verify')


    def verify(self, using_cache=False) -> bool:
        if using_cache and self.verify_by_cache():
            return True
        response = requests.post(
            self.get_verify_url(),
            json={
                'site_key': settings.ARCAPTCHA_SITE_KEY,
                'secret_key': settings.ARCAPTCHA_SECRET_KEY,
                'challenge_id': self.captcha_key,
            },
            timeout=10,
        )
        response.raise_for_status()
        if not response.json().get('success'):
            raise CaptchaProviderError(self.__class__.__name__)
        if using_cache:
            self.cache_captcha_validation()
        return True


class GeeTestCaptcha(BaseCaptcha):
    @classmethod
    def get_verify_url(cls):
        return f'http://gcaptcha4.geetest.com/validate?captcha_id={settings.GEETEST_CAPTCHA_ID}'

    def _get_payload(self) -> dict:
        import hmac
        lot_number = self.extra_data['lot_number']
        captcha_output = self.extra_data['captcha_output']
        pass_token = self.extra_data['pass_token']
        gen_time = self.extra_data['gen_time']  # TODO raise malformed error. One of these is captcha code.
        lotnumber_bytes = lot_number.encode()
        prikey_bytes = settings.GEETEST_CAPTCHA_KEY.encode()
        sign_token = hmac.new(prikey_bytes, lotnumber_bytes, digestmod='SHA256').hexdigest()
        return {
            "lot_number": lot_number,
            "captcha_output": captcha_output,
            "pass_token": pass_token,
            "gen_time": gen_time,
            "sign_token": sign_token,
        }

    def verify(self, using_cache=False) -> bool:
        if using_cache and self.verify_by_cache():
            return True
        response = requests.post(
            self.get_verify_url(),
            json=self._get_payload(),
            proxies=settings.DEFAULT_PROXY,
            timeout=5,
        )
        response.raise_for_status()
        if not response.json().get('result') == 'success':
            raise CaptchaProviderError(self.__class__.__name__)
        if using_cache:
            self.cache_captcha_validation()
        return True


class DjangoCaptcha(BaseCaptcha):
    @staticmethod
    def generate() -> tuple:
        method = Settings.get_value('captcha_pick_method') or settings.CAPTCHA_PICK_DEFAULT_METHOD
        key = CaptchaStore.pick(method=method, sample_rate=settings.CAPTCHA_PICK_SAMPLE_RATE)
        image_url = captcha_image_url(key)
        return key, image_url

    def verify(self, using_cache=False) -> bool:
        if using_cache and self.verify_by_cache():
            return True
        key = self.key  # TODO
        value = normalize_digits(self.captcha_key or '').lower().replace(' ', '')
        captcha_store = CaptchaStore.objects.filter(response=value, hashkey=key, expiration__gte=timezone.now()).first()
        if captcha_store:
            if using_cache:
                self.cache_captcha_validation()
            captcha_store.delete()
            return True
        return False


class CaptchaHandler:
    MAPPING: ClassVar = {
        'django-captcha': DjangoCaptcha,
        'recaptcha': ReCaptcha,
        'hcaptcha': HCaptcha,
        'arcaptcha': ARCaptcha,
        'geetest': GeeTestCaptcha,
    }

    def __init__(
        self,
        country: str,
        client: str,
        captcha_type: str,
        ip: str,
        captcha_key: str,
        key: str,
        url_path: str,
        extra_data: dict = None,
        check_type=False,
        usage: Optional[str] = None,
    ):
        self.country = country
        self.client = client
        self.captcha_type = captcha_type
        self.ip = ip
        self.check_type = check_type
        self.captcha_key = captcha_key
        self.extra_data = extra_data
        self.key = key
        self.usage = usage
        self.url_path = url_path

    @property
    def usage_based_on_url_path(self):
        if self.url_path:
            if 'login' in self.url_path:
                return 'login'
            elif 'registration' in self.url_path:
                return 'registration'
            elif 'forget-password' in self.url_path:
                return 'forget-password'
            elif 'request-tfa-removal' in self.url_path:
                return 'request-tfa-removal'
            elif 'confirm-tfa-removal' in self.url_path:
                return 'confirm-tfa-removal'
            elif 'otp/request-public' in self.url_path:
                return 'otp-request-public'
            elif 'gift/redeem-lightning' in self.url_path:
                return 'gift-redeem-lightning'
            elif 'gift/redeem' in self.url_path:
                return 'gift-redeem'
            elif 'marketing/suggestion/add' in self.url_path:
                return 'marketing-suggestion-add'
            elif 'profile-edit' in self.url_path:
                return 'profile-edit'
            else:
                'undefined'
        else:
            return 'undefined'

    @classmethod
    def get_all_types(cls) -> List[str]:
        return list(cls.MAPPING.keys())

    @classmethod
    def get_acceptable_types(cls, country: str, usage: Optional[str] = None) -> List[str]:
        """Return all captcha types that the user sending this request can use, in order
            of server preference.

        Note: This method is called in multiple separate user requests, so it should
        only consider attributes like IP that usually do not change among requests in
        a short time span.
        """

        if usage is not None:
            country_key = 'IR' if country == 'IR' else 'NON_IR'
            captcha_usage_configs = Settings.get_cached_json(
                'captcha_usage_configs_v2',
                DEFAULT_CAPTCHA_USAGE_CONFIGS_V2,
            )[country_key]

            return captcha_usage_configs.get(usage, captcha_usage_configs['default'])['types']

        if country == 'IR':
            return Settings.get_cached_json(
                'login_captcha_types_ir',
                default=cls.get_all_types(),
            )

        return Settings.get_cached_json(
            'login_captcha_types',
            default=cls.get_all_types(),
        )

    def verify(self, using_cache=False) -> bool:
        if settings.DISABLE_RECAPTCHA:
            return True

        if self.check_type:
            acceptable_types = self.get_acceptable_types(country=self.country, usage=self.usage)
            if self.captcha_type not in acceptable_types:
                raise UnacceptableCaptchaTypeError(acceptable_types=acceptable_types)
        captcha_class = self.MAPPING.get(self.captcha_type, DjangoCaptcha)
        metric_key = captcha_class.__name__
        if captcha_class.__name__ == 'DjangoCaptcha':
            metric_key += 'Farsi' if has_farsi_chars(self.captcha_key or '') else 'English'

        try:
            instance = captcha_class(ip=self.ip, client=self.client, captcha_key=self.captcha_key, key=self.key,
                                     extra_data=self.extra_data)
            result = instance.verify(using_cache=using_cache)
            metric_incr(f'metric_rawcaptcha__{metric_key}_{result}_{self.usage_based_on_url_path}')
        except CaptchaError as ex:
            metric_incr(f'metric_rawcaptcha__{metric_key}_{ex.__class__.__name__}_{self.usage_based_on_url_path}')
            return False
        except Exception as ex:
            report_exception()
            metric_incr(f'metric_rawcaptcha__{metric_key}_{ex.__class__.__name__}_{self.usage_based_on_url_path}')
            return False

        return result


