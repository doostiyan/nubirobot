""" API Manager """
from django.core.cache import cache


class APIManager:
    """ Ratelimiting utilities for external APIs
    """

    @classmethod
    def get_cache_key(cls, service, endpoint=None, token=None):
        key = 'apicall_{}'.format(service)
        if endpoint:
            key += '_' + endpoint
        if token:
            key += '_' + token
        return key

    @classmethod
    def log_call(cls, service, endpoint=None, token=None, n=1, limit=None):
        cache_key = cls.get_cache_key(service, endpoint=endpoint, token=token)
        if limit:
            calls = cache.get(cache_key) or 0
            if calls >= limit:
                return False
        try:
            cache.incr(cache_key, n)
        except ValueError:
            cache.set(cache_key, n)
        return True

    @classmethod
    def get_calls_count(cls, *args, **kwargs):
        return cache.get(cls.get_cache_key(*args, **kwargs)) or 0

    @classmethod
    def reset_calls_count(cls, *args, value=0, **kwargs):
        return cache.set(cls.get_cache_key(*args, **kwargs), value)
