from contextlib import contextmanager

import redis
from django.conf import settings
from django.core.cache import caches
from django_redis import get_redis_connection

from ..exception import catch_all_exceptions


class CacheUtils:
    DEFAULT_TIMEOUT = settings.CACHE_DEFAULT_TIMEOUT
    DEFAULT_CACHE_NAME = 'default'

    @staticmethod
    def read_from_local_cache(key, cache_name=DEFAULT_CACHE_NAME):
        return CacheUtils._read_from_cache(key, cache_name)

    @staticmethod
    @catch_all_exceptions()
    def read_from_external_cache(key, cache_name=DEFAULT_CACHE_NAME):
        return CacheUtils._read_from_cache(key, cache_name)

    @staticmethod
    def _read_from_cache(key, cache_name=DEFAULT_CACHE_NAME):
        cache = caches[cache_name]
        return cache.get(key)

    @staticmethod
    def write_to_local_cache(key, value, cache_name=DEFAULT_CACHE_NAME, timeout=DEFAULT_TIMEOUT):
        CacheUtils._write_to_cache(key, value, cache_name, timeout)

    @staticmethod
    def write_to_external_cache(key, value, cache_name=DEFAULT_CACHE_NAME, timeout=DEFAULT_TIMEOUT):
        CacheUtils._write_to_cache(key, value, cache_name, timeout)

    @staticmethod
    def _write_to_cache(key, value, cache_name=DEFAULT_CACHE_NAME, timeout=DEFAULT_TIMEOUT):
        cache = caches[cache_name]
        cache.set(key, value, timeout=timeout)

    @staticmethod
    def delete_from_local_cache(key, cache_name=DEFAULT_CACHE_NAME):
        return CacheUtils._delete_from_cache(key, cache_name)

    @staticmethod
    @catch_all_exceptions()
    def delete_from_external_cache(key, cache_name=DEFAULT_CACHE_NAME):
        return CacheUtils._delete_from_cache(key, cache_name)

    @staticmethod
    def _delete_from_cache(key, cache_name=DEFAULT_CACHE_NAME):
        cache = caches[cache_name]
        return cache.delete(key)


@contextmanager
def redis_lock(lock_key, timeout=10):
    conn = get_redis_connection("default")
    lock = conn.lock(lock_key, timeout=timeout)
    acquired = lock.acquire(blocking=True)
    try:
        if acquired:
            yield
        else:
            raise Exception("Could not acquire Redis lock")
    finally:
        if acquired:
            lock.release()

redis_client = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, password=settings.REDIS_PASSWORD)