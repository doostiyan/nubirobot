"""
This module provide a decorator for handling idempotency in internal services.
"""

import functools
import json
import typing
import uuid
from hashlib import sha256

from django.http import HttpRequest, HttpResponse, JsonResponse
from django_redis import get_redis_connection
from redis import Redis
from rest_framework.request import Request

__all__ = [
    'IDEMPOTENCY_HEADER',
    'idempotent',
]


IDEMPOTENCY_HEADER = 'idempotency-key'
CACHED_RESPONSE_TTL = 60 * 60 * 24


class CachedHTTPResponse:
    def __init__(
        self,
        response: HttpResponse,
    ) -> None:
        self.status_code = response.status_code
        self.payload = response.content.decode()
        self.headers = response.headers

    def serialize(self) -> str:
        return json.dumps(
            {
                'status_code': self.status_code,
                'payload': self.payload,
                'headers': dict(self.headers),
            }
        )

    @classmethod
    def deserialize(cls, payload: str) -> 'HttpResponse':
        kwargs = json.loads(payload)
        return HttpResponse(content=kwargs['payload'].encode(), status=kwargs['status_code'], headers=kwargs['headers'])


class CachedDictResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def serialize(self) -> str:
        return json.dumps(self.payload)

    @classmethod
    def deserialize(cls, payload: str) -> dict:
        return json.loads(payload)


class CachedJsonResponse:
    def __init__(self, payload: JsonResponse) -> None:
        self.payload = payload

    def serialize(self) -> str:
        return json.dumps(self.payload)

    @classmethod
    def deserialize(cls, payload: str) -> JsonResponse:
        return json.loads(payload)


class IdempotencyUtilities:
    @staticmethod
    def _cache_key(key: str, path: str, method: str) -> str:
        return sha256(f'idempotency_{method.upper()}_{path}_{key}'.encode()).hexdigest()

    @staticmethod
    @functools.lru_cache(maxsize=1)
    def _get_redis_client() -> Redis:
        return get_redis_connection()

    @staticmethod
    def get_cached_value(key: str, path: str, method: str) -> typing.Optional[str]:
        cached_response_payload = IdempotencyUtilities._get_redis_client().eval(
            '''
            local exists = redis.call('EXISTS', KEYS[1])
            if (exists == 1) then
                return redis.call('GET', KEYS[1])
            else
                redis.call('SET', KEYS[1], 'waiting', 'PX', 60)
                return 'new'
            end
        ''',
            1,
            IdempotencyUtilities._cache_key(key, path, method),
        )
        if cached_response_payload == b'new':
            return None
        if cached_response_payload == b'waiting':
            raise ValueError('Other process has locked this request')
        return cached_response_payload.decode()

    @staticmethod
    def set_cached_value(key: str, payload: str, path: str, method: str) -> None:
        IdempotencyUtilities._get_redis_client().set(
            IdempotencyUtilities._cache_key(key, path, method),
            payload,
            CACHED_RESPONSE_TTL,
        )

    @staticmethod
    def delete_cached_value(key: str, path: str, method: str) -> None:
        IdempotencyUtilities._get_redis_client().delete(IdempotencyUtilities._cache_key(key, path, method))

    @staticmethod
    def is_valid(key: str) -> bool:
        try:
            _ = uuid.UUID(key)
        except ValueError:
            return False
        return True


def idempotent(view):
    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        is_class_view = False
        if isinstance(args[0], (HttpRequest, Request)):
            request = args[0]
        elif isinstance(args[1], (HttpRequest, Request)):
            is_class_view = True
            request = args[1]
        else:
            raise NotImplementedError('incompatible view: `request` should be first or second `arg` of view')

        idempotency_key = request.headers.get(IDEMPOTENCY_HEADER.upper().replace('-', '_'))
        if idempotency_key is None:
            return JsonResponse(
                status=400, data={'status': 'failed', 'code': 'MissingIdempotencyKey'}
            )
        if not IdempotencyUtilities.is_valid(idempotency_key):
            return JsonResponse(
                status=400, data={'status': 'failed', 'code': 'InvalidIdempotencyKey'}
            )

        method = request.META['REQUEST_METHOD']
        path = request.META['PATH_INFO']

        try:
            response_payload = IdempotencyUtilities.get_cached_value(idempotency_key, path, method)
        except ValueError:
            return JsonResponse(
                status=409, data={'status': 'failed', 'code': 'ConcurrentIdempotentRequest'}
            )

        cached_response_class = CachedHTTPResponse if is_class_view else CachedDictResponse

        if response_payload is not None:
            return cached_response_class.deserialize(response_payload)

        try:
            response: typing.Union[dict, JsonResponse] = view(*args, **kwargs)
            is_http_response = isinstance(response, HttpResponse)
            if (is_http_response and response.status_code == 200) or not is_http_response:
                IdempotencyUtilities.set_cached_value(
                    idempotency_key, cached_response_class(response).serialize(), path, method
                )
        except:
            IdempotencyUtilities.delete_cached_value(idempotency_key, path, method)
            raise

        return response

    return wrapped_view
