import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import jwt
from Crypto.PublicKey import RSA
from django.test import RequestFactory, override_settings
from rest_framework.test import APITestCase

from exchange.base.api_v2_1 import InternalAPIView, internal_post_api
from exchange.base.internal.permissions import AllowedServices
from exchange.base.internal.services import Services

_PRIVATE_KEY = RSA.generate(2048)
PRIVATE_KEY = _PRIVATE_KEY.export_key()
PUBLIC_KEY = _PRIVATE_KEY.public_key().export_key()
DUMMY_PUBLIC_KEY = RSA.generate(2048).public_key().export_key()


@internal_post_api(allowed_services={Services.ABC}, _idempotent=False)
def dummy_function_view(request):
    return {'service': request.service}


class DummyClassView(InternalAPIView):
    permission_classes = [AllowedServices({Services.ABC})]

    def post(self, request):
        return self.response({'service': request.service})


@override_settings(INTERNAL_JWT_PUBLIC_KEYS=[DUMMY_PUBLIC_KEY, PUBLIC_KEY], IS_INTERNAL_INSTANCE=True)
class TestInternalJWTDecorator(APITestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _create_token(self, key, service: Services, token_id='', *, is_expired=False):
        exp = datetime.now(tz=timezone.utc) - (timedelta(days=1) if is_expired else -timedelta(days=1))
        payload = {
            'jti': token_id or str(uuid4()),
            'service': service,
            'exp': exp.timestamp(),
        }
        return jwt.encode(payload, key=key, algorithm='RS256')

    def _test_internal_jwt_decorator(self, view, token=None, status=200, result=None):
        token = token or self._create_token(PRIVATE_KEY, Services.ABC, is_expired=False)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        request = self.factory.post('/test-path', **headers)
        response = view(request)
        assert response is not None
        assert response.status_code == status, response
        if status == 200:
            assert json.loads(response.content) == result

    def assert_ok(self, view, result, token=None):
        return self._test_internal_jwt_decorator(view, token=token, result=result)

    def assert_failed(self, view, status, token=None):
        return self._test_internal_jwt_decorator(view, token=token, status=status)

    @patch('exchange.base.internal.authentications.is_nobitex_server_ip', lambda _: True)
    def test_internal_jwt_decorator_on_function_view(self):
        self.assert_ok(dummy_function_view, result={'service': 'abc'})

    @patch('exchange.base.internal.authentications.is_nobitex_server_ip', lambda _: True)
    def test_internal_jwt_decorator_on_class_view(self):
        self.assert_ok(DummyClassView.as_view(), result={'service': 'abc'})

    @override_settings(INTERNAL_JWT_PUBLIC_KEYS=[DUMMY_PUBLIC_KEY])
    @patch('exchange.base.internal.authentications.is_nobitex_server_ip', lambda _: True)
    def test_internal_jwt_decorator_invalid_signature(self):
        self.assert_failed(dummy_function_view, status=404)

    @patch('exchange.base.internal.authentications.is_nobitex_server_ip', lambda _: False)
    def test_internal_jwt_decorator_invalid_ip(self):
        self.assert_failed(dummy_function_view, status=404)

    @patch('exchange.base.internal.authentications.is_nobitex_server_ip', lambda _: True)
    def test_internal_jwt_decorator_expired_token(self):
        token = self._create_token(PRIVATE_KEY, Services.ABC, is_expired=True)
        self.assert_failed(dummy_function_view, token=token, status=404)

    @patch('exchange.base.internal.authentications.is_nobitex_server_ip', lambda _: True)
    def test_internal_jwt_decorator_without_token(self):
        request = self.factory.post('/test-path')
        response = dummy_function_view(request)
        assert response is not None
        assert response.status_code == 404

    @patch('exchange.base.internal.authentications.is_nobitex_server_ip', lambda _: True)
    def test_internal_jwt_decorator_invalid_token(self):
        headers = {'HTTP_Authorization': 'Token'}
        request = self.factory.post('/test-path', **headers)
        response = dummy_function_view(request)
        assert response is not None
        assert response.status_code == 404

    @patch('exchange.base.internal.authentications.is_nobitex_server_ip', lambda _: True)
    def test_internal_jwt_decorator_blacklisted_token(self):
        token_id = str(uuid4())
        token = self._create_token(PRIVATE_KEY, Services.ABC, token_id=token_id, is_expired=False)
        self.assert_ok(dummy_function_view, token=token, result={'service': 'abc'})

        with override_settings(BLACKLIST_JWTS={token_id}):
            self.assert_failed(dummy_function_view, token=token, status=404)

    @patch('exchange.base.internal.authentications.is_nobitex_server_ip', lambda _: True)
    def test_internal_jwt_decorator_disallowed_service(self):
        token = self._create_token(PRIVATE_KEY, 'admin', is_expired=False)
        self.assert_failed(dummy_function_view, token=token, status=403)

    @patch('exchange.base.internal.authentications.is_nobitex_server_ip', lambda _: True)
    def test_internal_jwt_decorator_disallowed_service_in_class_view(self):
        token = self._create_token(PRIVATE_KEY, 'admin', is_expired=False)
        self.assert_failed(DummyClassView.as_view(), token=token, status=403)

    @patch('exchange.base.internal.authentications.is_nobitex_server_ip', lambda _: True)
    def test_internal_jwt_decorator_null_service_in_token(self):
        exp = datetime.now(tz=timezone.utc) + timedelta(days=1)
        payload = {
            'tokenId': str(uuid4()),
            'exp': exp.timestamp(),
        }
        token = jwt.encode(payload, key=PRIVATE_KEY, algorithm='RS256')
        self.assert_failed(dummy_function_view, token=token, status=404)
