import functools
from datetime import datetime, timedelta, timezone
from random import randint
from typing import Optional
from uuid import uuid4

import jwt
from django.conf import settings
from django.test import override_settings
from pyparsing import wraps
from rest_framework.test import APIClient, APITestCase

from exchange.base.internal.idempotency import IDEMPOTENCY_HEADER
from exchange.base.internal.services import Services

INTERNAL_TEST_PRIVATE_KEY = '''
-----BEGIN RSA PRIVATE KEY-----
MIIBOgIBAAJBAMcSjXbWO6B7pbMPcqTzQrZmjvwqWYeEH6XNtlZ7xSjnG8+UKrxw
4rdP8VwsODHJNWd1trKStcZjfixFI5CHqnsCAwEAAQJAIc4Tub9thrYYkEyqQjqQ
9Jp743RpmaqlGSnSseL4uxYe+ZdVlmeC/Kf53jg/KESF1gpRte0EmGZDHIpuveNU
sQIhAPF4NEYXiuQ7pGn6Uj8RmZ+HMO0om9UwWUoaH1hqiSfZAiEA0w06menb6OcG
leSBcvXp7ho7i7ls/EuJWh9Q2T3qZHMCIALnQxmkptLftLZhgCOp/oLgiUIQvu7t
SeWOMtpJTaThAiAkpcNrPoSFKLioBonD4JfCVKPKW2RlWuh60b1EO9AbqQIhAMPR
2LryyIKuW+wfGDnCQZF/XgjVvrRtwSyIVvKLpedo
-----END RSA PRIVATE KEY-----
'''

INTERNAL_TEST_PUBLIC_KEY = '''
-----BEGIN PUBLIC KEY-----
MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAMcSjXbWO6B7pbMPcqTzQrZmjvwqWYeE
H6XNtlZ7xSjnG8+UKrxw4rdP8VwsODHJNWd1trKStcZjfixFI5CHqnsCAwEAAQ==
-----END PUBLIC KEY-----
'''


def create_internal_token(service: str, exp: Optional[datetime] = None):
    return jwt.encode(
        payload=dict(exp=exp or datetime.now() + timedelta(minutes=1), service=service, jti=randint(10 ** 8, 10 ** 9)),
        algorithm='RS256',
        key=INTERNAL_TEST_PRIVATE_KEY,
    )


def mock_internal_service_settings(f):
    """
    This decorator overrides specific settings to simulate an internal service environment.
    It modifies settings related to JWT public keys, server IPs, and instance type,
    and applies a Redis cache configuration for the decorated function.
    """

    @wraps(f)
    @override_settings(
        INTERNAL_JWT_PUBLIC_KEYS=[INTERNAL_TEST_PUBLIC_KEY],
        NOBITEX_SERVER_IPS=['0.0.0.0/0'],
        IS_INTERNAL_INSTANCE=True,
    )
    @use_redis_cache
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)

    return wrapper


def use_redis_cache(test):
    """
    This decorator overrides the cache settings to use a Redis backend instead of default MemCache.
    """

    @functools.wraps(test)
    @override_settings(
        CACHES={
            'default': {
                'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': f'redis://{settings.REDIS_HOST}/{settings.REDIS_DB_NO + 10}',
                'TIMEOUT': None,
                'OPTIONS': {
                    'PICKLE_VERSION': 4,
                },
            },
        },
    )
    def decorated(*args, **kwargs):
        return test(*args, **kwargs)

    return decorated


class APIClientIdempotency(APIClient):
    """
    A subclass of APIClient that adds idempotency headers to HTTP methods.

    This class ensures that idempotency headers are added to HTTP methods (POST, PUT, PATCH, DELETE)
    if they do not already exist in the request headers. This helps to avoid duplicate requests
    and ensures that the server processes each request only once.
    """

    @staticmethod
    def _add_idempotency_headers_if_not_exists(**kwargs):
        headers = kwargs.get('headers', {})
        if headers.get(IDEMPOTENCY_HEADER):
            return kwargs

        headers.update({IDEMPOTENCY_HEADER: str(uuid4())})
        kwargs['headers'] = headers
        return kwargs

    def post(self, *args, **kwargs):
        kwargs = self._add_idempotency_headers_if_not_exists(**kwargs)
        return super().post(*args, **kwargs)

    def put(self, *args, **kwargs):
        kwargs = self._add_idempotency_headers_if_not_exists(**kwargs)
        return super().post(*args, **kwargs)

    def patch(self, *args, **kwargs):
        kwargs = self._add_idempotency_headers_if_not_exists(**kwargs)
        return super().post(*args, **kwargs)

    def delete(self, *args, **kwargs):
        kwargs = self._add_idempotency_headers_if_not_exists(**kwargs)
        return super().post(*args, **kwargs)


class APITestCaseWithIdempotency(APITestCase):
    client_class = APIClientIdempotency


class InternalAPITestMixin:
    def _request(self, *args, **kwargs):
        raise NotImplementedError()

    @mock_internal_service_settings
    def test_internal_api_without_token(self):
        self.client.credentials(HTTP_AUTHORIZATION=None)

        response = self._request()
        assert response.status_code == 404
        assert response.json() == {'detail': 'یافت نشد.'}

    @mock_internal_service_settings
    def test_internal_api_token_expired(self):
        exp = datetime.now(timezone.utc) - timedelta(seconds=100)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_internal_token(Services.ABC.value, exp=exp)}',
        )

        response = self._request()
        assert response.status_code == 404
        assert response.json() == {'detail': 'یافت نشد.'}

    @mock_internal_service_settings
    @override_settings(NOBITEX_SERVER_IPS=['1.1.1.1'])
    def test_internal_api_invalid_ip(self):
        response = self._request()
        assert response.status_code == 404
        assert response.json() == {'detail': 'یافت نشد.'}

    @mock_internal_service_settings
    @override_settings(INTERNAL_JWT_PUBLIC_KEYS=[])
    def test_internal_api_invalid_token_signature(self):
        response = self._request()
        assert response.status_code == 404
        assert response.json() == {'detail': 'یافت نشد.'}

    @mock_internal_service_settings
    @override_settings(IS_INTERNAL_INSTANCE=False)
    def test_internal_api_not_internal_instance(self):
        response = self._request()
        assert response.status_code == 404
        assert response.json() == {'detail': 'یافت نشد.'}
