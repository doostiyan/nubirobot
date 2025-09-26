from functools import wraps

from cachetools import Cache, TTLCache
from django.conf import settings

MAX_REPORT_PER_MIN = 1


try:
    from cachetools.ttl import _Link

    class CustomTTLCache(TTLCache):
        def __setitem__(self, key, value, cache_setitem=Cache.__setitem__):
            """
            Overrides the __setitem__ method to change behavior of expiration of items,
            This will keep expiration time of existing items instead of resting it.
            """
            with self._TTLCache__timer as time:
                self.expire(time)
                cache_setitem(self, key, value)

            try:
                link = self._TTLCache__getlink(key)
            except KeyError:
                self._TTLCache__links[key] = link = _Link(key)
                link.expire = time + self.ttl
            else:
                link.unlink()
            link.next = root = self._TTLCache__root
            link.prev = prev = root.prev
            prev.next = root.prev = link


except ImportError:  #  for cachetools >= 5.0.0

    class CustomTTLCache(TTLCache):
        def __setitem__(self, key, value, cache_setitem=Cache.__setitem__):
            """
            Overrides the __setitem__ method to change behavior of expiration of items,
            This will keep expiration time of existing items instead of resting it.
            """
            with self.timer as time:
                self.expire(time)
                cache_setitem(self, key, value)
            try:
                link = self._TTLCache__getlink(key)
            except KeyError:
                self._TTLCache__links[key] = link = TTLCache._Link(key)
                link.expires = time + self.ttl
            else:
                link.unlink()
            link.next = root = self._TTLCache__root
            link.prev = prev = root.prev
            prev.next = root.prev = link


sentry_cache = CustomTTLCache(maxsize=100, ttl=60)


def should_drop_event(event) -> bool:
    try:
        if event['level'] == 'info':
            filename = event.get('transaction', 'undefined-path')
            error = event['message']
            line_no = 'info'
        elif event['level'] == 'error':
            frame = event['exception']['values'][0]['stacktrace']['frames'][-1]
            error = event['exception']['values'][0]['type']
            filename = frame['filename']
            line_no = frame['lineno']
        else:
            return False
    except KeyError:
        # Send unknown events
        return False

    key = f'{filename}:{line_no}:{error}' if error != 'BusyLoadingError' else str(error)
    error_count = sentry_cache.get(key) or 0
    sentry_cache[key] = error_count + 1
    if error_count <= MAX_REPORT_PER_MIN or error_count % 32 == 0:
        return False
    return True


def before_send(event, hint):
    try:
        if should_drop_event(event):
            return None  # Returning None indicates that the event should be dropped
    except Exception as ex:  # noqa: BLE001
        print(f'Sentry Limiter exception: {ex}')

    return event


class sentry_transaction_sample_rate:
    """
    A decorator for overriding sentry transaction_sample_rate for specefic APIs.

    Example:
    >>> @sentry_transaction_sample_rate(rate=0.125)
    >>> @api
    >>> def sample_view(*args, **kwargs)
    """

    API_MAPPING_TRANSACTION_SAMPLE_RATE_MAPPING = {}

    def __init__(self, rate: float):
        self.rate = rate

    def __call__(self, func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            self.API_MAPPING_TRANSACTION_SAMPLE_RATE_MAPPING[(request.method, request.path)] = self.rate
            return func(request, *args, **kwargs)
        return wrapper


def traces_sampler(sampling_context):
    if sampling_context.get('parent_sampled'):  # if parent transaction is traced, this transaction should be traced too
        return 1.0
    if (
        'wsgi_environ' in sampling_context
        and 'REQUEST_METHOD' in sampling_context['wsgi_environ']
        and 'PATH_INFO' in sampling_context['wsgi_environ']
    ):  # request method and path are stored in wsgi_environ in sampling_context
        return sentry_transaction_sample_rate.API_MAPPING_TRANSACTION_SAMPLE_RATE_MAPPING.get(
            (sampling_context['wsgi_environ']['REQUEST_METHOD'], sampling_context['wsgi_environ']['PATH_INFO']),
            settings.SENTRY_TRACES_SAMPLE_RATE,
        )

    # return the default value when WSGI is not used or to avoid dependency on it.
    return settings.SENTRY_TRACES_SAMPLE_RATE
