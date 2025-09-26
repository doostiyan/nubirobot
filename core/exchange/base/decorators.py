import contextlib
import json
from collections import defaultdict
from functools import partial, wraps
from time import time
from typing import Callable, Optional

import django
from django.conf import settings
from django.core.cache import cache

from exchange.base.api import is_internal_ip
from exchange.base.logging import log_time, log_time_without_avg, metric_incr, report_exception


def cached_method(func=None, timeout=60):
    def decorator(func):
        def wrapper(*args, skip_cache=False, **kwargs):
            params = []
            for i, key in enumerate(func.__code__.co_varnames):
                if i == 0 and key in ('self', 'cls'):
                    continue
                params.append(f'{key}={args[i] if i < len(args) else kwargs.get(key)}')
            cache_key = f'{func.__module__}.{func.__qualname__}?{"&".join(params)}'
            cache_version = django.get_version()
            if not skip_cache:
                value = cache.get(cache_key, version=cache_version)
                if value:
                    return value
            value = func(*args, **kwargs)
            cache.set(cache_key, value, timeout, version=cache_version)
            return value
        return wrapper
    if func:
        return decorator(func)
    return decorator


class SkipCache(Exception):
    pass


def ram_cache(timeout=60, default=None):
    """ Cache function results in RAM

    It uses arguments to cache data and ignores keyword arguments.
    Note: Do not pass arguments as keyword arguments!!!
    """

    def decorator(func):
        cached_data = {}
        last_update = {}

        def wrapper(*args, skip_cache=False, **kwargs):
            ram_cache_age = time() - last_update.get(args, 0)
            if ram_cache_age > timeout or skip_cache:
                try:
                    cached_data[args] = func(*args, **kwargs)
                except SkipCache:
                    pass
                except:
                    report_exception()
                finally:
                    last_update[args] = time()
            return cached_data.get(args, default)

        def clear_cache():
            cached_data.clear()
            last_update.clear()

        wrapper.clear = clear_cache

        return wrapper

    return decorator


def measure_time(func=None, metric=None, verbose=True):
    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time()
            result = func(*args, **kwargs)
            duration = int((time() - start) * 1000)
            log_time(str(metric) or func.__qualname__, duration)
            if verbose:
                print(f'{str(result):<80}[{duration:>5}ms]')
            return result
        return wrapper
    if func:
        return decorator(func)
    return decorator


class measure_time_cm(contextlib.ContextDecorator):
    def __init__(self, metric: str, labels: Optional[tuple] = None, callback: Optional[Callable] = None, **kwargs):
        self.metric = metric
        self.labels = labels
        self.start_time = None
        self.callback = callback
        self.kwargs = kwargs

    def __enter__(self):
        self.start_time = time()

    def __exit__(self, exc_type, exc_value, traceback):
        duration = int((time() - self.start_time) * 1000)
        log_time(self.metric, duration, self.labels)
        if callable(self.callback):
            self.callback(duration, **self.kwargs)


class measure_success_time_cm(measure_time_cm):
    def __exit__(self, exc_type, exc_value, traceback):
        if exc_value:
            return
        super().__exit__(exc_type, exc_value, traceback)


class measure_function_execution(contextlib.ContextDecorator):
    """
    A context manager and decorator for aggregation the count and time of a function and log it into metric cache.

    This class is used to measure the count, processing time, and end-to-end latency of messages processed by a function.
    It logs the metrics at specified intervals.

    Parameters:
    -----------
    metric : str
        The base label of the metric to be logged.
    metric_prefix:
        The prefix of metrics.
    metrics_flush_interval : int, optional
        The interval in seconds at which metrics are logged (default is 30).

    NOTE: You NEED to add these metrics to report/view.py to export the metrics if not exits:
        - {metric_prefix}_process_count
        - {metric_prefix}_process_time
        - {metric_prefix}_e2e_latency (optional, only for consumers)

    Example:
        >>> @measure_function_execution('notificationList', metric_prefix='api', metrics_flush_interval=10)
        >>> @api
        >>> def notification_list(msg, *args, **kwargs)
    """

    COUNT_METRIC_KEY = 'metric_%s_process_count__%s'
    PROCESS_TIME_METRIC_KEY = '%s_process_time__%s'
    E2E_LATENCY_METRIC_KEY = '%s_e2e_latency__%s'

    last_commit_time = time()

    process_time_metrics_store = {}
    e2e_latency_metrics_store = {}
    counter_metrics_store = defaultdict(int)

    def __init__(
        self, metric: str, metric_prefix: str, sampling_func: Optional[Callable] = None, metrics_flush_interval=30
    ):
        self.metric = metric
        self.metric_prefix = metric_prefix
        self.start_time = None
        self.metrics_flush_interval = metrics_flush_interval
        self.e2e_latency = None
        self.sampling_func = sampling_func
        self.args = None
        self.kwds = None

    def __enter__(self):
        self.start_time = time()

    def __exit__(self, exc_type, exc_value, traceback):
        if callable(self.sampling_func) and not self.sampling_func(*self.args, **self.kwds):
            return
        duration = int((time() - self.start_time) * 1000)
        self._log_metrics(duration)

    def __call__(self, func):
        @wraps(func)
        def inner(*args, **kwds):
            self.args = args
            self.kwds = kwds
            self.e2e_latency = kwds.get('e2e_latency')
            with self._recreate_cm():
                return func(*args, **kwds)

        return inner

    @property
    def count_metric_key(self):
        return self.COUNT_METRIC_KEY % (self.metric_prefix, self.metric)

    @property
    def process_time_metric_key(self):
        return self.PROCESS_TIME_METRIC_KEY % (self.metric_prefix, self.metric)

    @property
    def e2e_latency_metric_key(self):
        return self.E2E_LATENCY_METRIC_KEY % (self.metric_prefix, self.metric)

    def _log_metrics(self, duration: int):
        self.counter_metrics_store[self.count_metric_key] += 1
        count = self.counter_metrics_store[self.count_metric_key]

        if count == 1:
            self.process_time_metrics_store[self.process_time_metric_key] = duration
            if self.e2e_latency is not None:
                self.e2e_latency_metrics_store[self.e2e_latency_metric_key] = self.e2e_latency
        else:
            self.process_time_metrics_store[self.process_time_metric_key] = self.get_avg_process_time(duration, count)
            if self.e2e_latency is not None:
                self.e2e_latency_metrics_store[self.e2e_latency_metric_key] = self.get_avg_e2e_latency(count)

        if self.last_commit_time + self.metrics_flush_interval < time():
            try:
                self.last_commit_time = int(time())
                self.log_count()
                self.log_process_time()
                if self.e2e_latency is not None:
                    self.log_e2e_latency()

            except:  # noqa: E722
                report_exception()

    def get_avg_e2e_latency(self, count):
        return int(
            (self.e2e_latency_metrics_store[self.e2e_latency_metric_key] * (count - 1) + self.e2e_latency) / count,
        )

    def get_avg_process_time(self, duration, count):
        if self.process_time_metrics_store.get(self.process_time_metric_key) is None:
            self.process_time_metrics_store[self.process_time_metric_key] = duration
        return int((self.process_time_metrics_store[self.process_time_metric_key] * (count - 1) + duration) / count)

    def log_count(self):
        metric_incr(self.count_metric_key, amount=self.counter_metrics_store[self.count_metric_key])
        self.counter_metrics_store[self.count_metric_key] = 0

    def log_process_time(self):
        log_time_without_avg(
            self.process_time_metric_key, self.process_time_metrics_store[self.process_time_metric_key]
        )
        del self.process_time_metrics_store[self.process_time_metric_key]

    def log_e2e_latency(self):
        log_time_without_avg(self.e2e_latency_metric_key, self.e2e_latency_metrics_store[self.e2e_latency_metric_key])
        del self.e2e_latency_metrics_store[self.e2e_latency_metric_key]


class measure_consumer_execution(measure_function_execution):
    """
    A specialized context manager and decorator for measuring consumer metrics.

    This class is an extension of the `measure_count_and_time` class and is specifically tailored
    for measuring the count and processing time of messages processed by a consumer.
    It automatically uses the prefix 'consumer' for all metrics.

    Parameters:
    -----------
    consumer_label : str
        The label identifying the consumer for which metrics are being logged.
    metrics_flush_interval : int, optional
        The interval in seconds at which metrics are flushed and logged (default is 30).

    Example:
        >>> @measure_consumer_execution('email.creator', metrics_flush_interval=30)
        >>> def callback(msg, *args, **kwargs)

    Usage Notes:
    ------------
    - This class is intended for use in environments where consumer metrics need to be
      aggregated and logged, such as in message queue consumers.
    - Ensure that the metrics `consumer_process_count`, `consumer_process_time`, and optionally
      `consumer_e2e_latency` are defined in `report/view.py` for proper logging.
    """

    def __init__(self, consumer_label: str, metrics_flush_interval=30):
        super().__init__(
            metric=consumer_label,
            metric_prefix='consumer',
            metrics_flush_interval=metrics_flush_interval,
        )


class measure_api_execution(measure_function_execution):
    """
    A specialized context manager and decorator for measuring API metrics per server.

    This class extends the `measure_count_and_time` base class, adapting it for use with API endpoints.
    It automatically uses the prefix 'api' for all metrics, allowing for consistent metric tracking
    across various API operations.

    Parameters:
    -----------
    api_label : str
        The label identifying the API for which metrics are being logged.
    metrics_flush_interval : int, optional
        The interval in seconds at which metrics are flushed and logged (default is 30).

    Example:
        >>> @measure_api_execution('userInfo', metrics_flush_interval=30)
        >>> def get_user_info(request, *args, **kwargs)

    Usage Notes:
    ------------
    - This class is designed for use in Django or similar web frameworks to measure
      the count and processing time of API requests.
    - Ensure that the metrics `api_process_count` and `api_process_time` are defined in
      `report/view.py` for proper logging.
    - End-to-end latency metrics are not typically applicable for API endpoints, so
      they are not included by default in this setup.
    """

    COUNT_METRIC_KEY = 'metric_%s_process_count__%s_%s'
    COUNT_RESULT_METRIC_KEY = 'metric_%s_process_result_count__%s_%s_%s'
    PROCESS_TIME_METRIC_KEY = '%s_process_time__%s_%s'
    last_result_commit_time = time()

    def __init__(
        self,
        api_label: str,
        sampling_func: Optional[Callable] = None,
        metrics_flush_interval=30,
        with_result: bool = False,
    ):
        super().__init__(
            metric=f'{api_label}_{settings.SERVER_NAME}',
            metric_prefix='api',
            sampling_func=sampling_func,
            metrics_flush_interval=metrics_flush_interval,
        )
        self.api_label = api_label
        self.response = None
        self.status_code = None
        self.with_result = with_result

    def __call__(self, func):
        @wraps(func)
        def inner(*args, **kwds):
            with self._recreate_cm():
                self.args = args
                self.kwds = kwds
                result = func(*args, **kwds)
                self.response = result
                self.status_code = result.status_code
                return result

        return inner

    @property
    def count_metric_key(self):
        return self.COUNT_METRIC_KEY % (self.metric_prefix, self.metric, self.status_code)

    @property
    def process_time_metric_key(self):
        return self.PROCESS_TIME_METRIC_KEY % (self.metric_prefix, self.metric, self.status_code)

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type:
            self.status_code = 500
        self.log_result()
        super().__exit__(exc_type, exc_value, traceback)

    def log_result(self):

        if not self.with_result:
            return
        self.counter_metrics_store[self.count_result_metric_key] += 1

        if self.last_result_commit_time + self.metrics_flush_interval < time():
            try:
                self.last_result_commit_time = int(time())
                self.log_result_count()
            except:  # noqa: E722
                report_exception()

    def log_result_count(self):
        metric_incr(self.count_result_metric_key, amount=self.counter_metrics_store[self.count_result_metric_key])
        self.counter_metrics_store[self.count_result_metric_key] = 0

    @property
    def result(self):
        try:
            payload = json.loads(self.response.content.decode())
        except Exception:
            return 'unexpected'

        status = payload.get('status')
        if status == 'failed':
            return payload.get('code', 'NotKnown')
        elif status == 'ok':
            return 'success'
        return 'UnknownStatus'

    @property
    def count_result_metric_key(self) -> str:
        return self.COUNT_RESULT_METRIC_KEY % (
            self.metric_prefix,
            self.api_label,
            settings.SERVER_NAME,
            self.result,
        )

measure_internal_bot_api_execution = partial(
    measure_api_execution,
    sampling_func=lambda *args, **kwargs: is_internal_ip(args[0].META['REMOTE_ADDR']) if args else False,
)


class measure_cron_execution(measure_function_execution):
    COUNT_METRIC_KEY = 'metric_cron_process_count__%s_%s_%s'
    PROCESS_TIME_METRIC_KEY = 'cron_process_time__%s_%s_%s'

    def __init__(self, app: str, cron: str, metrics_flush_interval=30):
        super().__init__(
            metric=f'{app}_{cron}_status',
            metric_prefix='cron',
            metrics_flush_interval=metrics_flush_interval,
        )
        self.success = True
        self.app = app
        self.cron = cron

    @property
    def count_metric_key(self):
        return self.COUNT_METRIC_KEY % (self.app, self.cron, self.success)

    @property
    def process_time_metric_key(self):
        return self.PROCESS_TIME_METRIC_KEY % (self.app, self.cron, self.success)

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type:
            self.success = False
        super().__exit__(exc_type, exc_value, traceback)
