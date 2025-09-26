import json
import uuid

import pytest
from django.http import Http404, JsonResponse
from django.test import RequestFactory, TestCase

from exchange.base.api import ParseError, PublicAPIView, public_post_v2_api
from exchange.base.internal.idempotency import IdempotencyUtilities, idempotent
from tests.helpers import use_redis_cache


@use_redis_cache
def test_utilities():
    path = '/test/sdweeq$%34234@#23113413151'
    method = 'POST'

    key = uuid.uuid4().hex
    cache_key = IdempotencyUtilities._cache_key(key, path, method)
    redis_client = IdempotencyUtilities._get_redis_client()
    assert  redis_client.get(cache_key) is None
    assert IdempotencyUtilities.get_cached_value(key, path, method) is None
    assert redis_client.get(cache_key) == b'waiting'
    with pytest.raises(ValueError):
        IdempotencyUtilities.get_cached_value(key, path, method)
    IdempotencyUtilities.set_cached_value(key, 'someValue', path, method)
    assert IdempotencyUtilities.get_cached_value(key, path, method) == 'someValue'
    redis_client.set(cache_key, 'someValue', 111)


class IdempotencyDecoratorTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        @public_post_v2_api
        @idempotent
        def dummy_view(_):
            return {
                'status': 'ok',
                'result': 'someResult',
            }

        self.dummy_view = dummy_view

    @use_redis_cache
    def test_re_requesting(self):
        key = uuid.uuid4().hex
        request = self.factory.post('/test-path', HTTP_IDEMPOTENCY_KEY=key)
        response = self.dummy_view(request)
        assert response.status_code == 200
        assert response.content.decode() == json.dumps({
            'status': 'ok',
            'result': 'someResult',
        })

        def view_func(_):
            raise Exception

        dummy_view = public_post_v2_api(idempotent(view_func))
        response = dummy_view(request)
        assert response.status_code == 200
        assert response.content.decode() == json.dumps({
            'status': 'ok',
            'result': 'someResult',
        })

    @use_redis_cache
    def test_re_requesting_when_api_failed(self):
        @public_post_v2_api
        @idempotent
        def view_func(_):
            raise ParseError()

        key = uuid.uuid4().hex
        request = self.factory.post('/test-path', HTTP_IDEMPOTENCY_KEY=key)
        response = view_func(request)
        assert response.status_code == 400
        assert response.content.decode() == json.dumps(
            {
                'status': 'failed',
                'code': 'ParseError',
                'message': '',
            },
        )

        def view_func(_):
            return

        dummy_view = public_post_v2_api(idempotent(view_func))
        response = dummy_view(request)
        assert response.status_code == 200

    @use_redis_cache
    def test_class_based_view_re_requesting(self):
        key = uuid.uuid4().hex
        request = self.factory.post('/test-path?a=1&b=2,3#123as*(&%@)!*&', HTTP_IDEMPOTENCY_KEY=key)

        class View(PublicAPIView):
            @idempotent
            def post(self, request):
                return self.response({
                    'status': 'ok',
                    'result': 'someResult',
                })

        response = View().as_view()(request)
        assert response.status_code == 200
        assert response.content.decode() == json.dumps({
            'status': 'ok',
            'result': 'someResult',
        })

        class View(PublicAPIView):
            @idempotent
            def post(self, request):
                raise Exception

        response = View().as_view()(request)
        assert response.status_code == 200, response.content
        assert response.content.decode() == json.dumps({
            'status': 'ok',
            'result': 'someResult',
        })

    @use_redis_cache
    def test_404_error(self):
        key = uuid.uuid4().hex
        request = self.factory.post('/test-path', HTTP_IDEMPOTENCY_KEY=key)
        def view_func(_):
            raise Http404

        dummy_view = public_post_v2_api(idempotent(view_func))
        dummy_view(request)
        assert IdempotencyUtilities.get_cached_value(key, '/test-path', 'post') is None

    @use_redis_cache
    def test_concurrent_requests(self):
        key = uuid.uuid4().hex
        request = self.factory.post('/test-path', HTTP_IDEMPOTENCY_KEY=key)

        IdempotencyUtilities.set_cached_value(key, 'waiting', '/test-path', 'post')

        @idempotent
        def view_func(_):
            raise Exception

        response = view_func(request)

        assert response.status_code == 409
        assert response.content.decode() == json.dumps({
            'status': 'failed',
            'code': 'ConcurrentIdempotentRequest',
        })

    @use_redis_cache
    def test_missing_idempotency_key(self):
        request = self.factory.post('/test-path', {})
        response: JsonResponse = self.dummy_view(request)
        assert response.status_code == 400
        assert response.content.decode() == json.dumps({
            'status': 'failed',
            'code': 'MissingIdempotencyKey',
        })

    @use_redis_cache
    def test_invalid_idempotency_key(self):
        key = 'x' + uuid.uuid4().hex[1:]
        request = self.factory.post('/test-path', HTTP_IDEMPOTENCY_KEY=key)
        response: JsonResponse = self.dummy_view(request)
        assert response.status_code == 400
        assert response.content.decode() == json.dumps({
            'status': 'failed',
            'code': 'InvalidIdempotencyKey',
        })
