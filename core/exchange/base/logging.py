import logging
import sys
import traceback
from decimal import Decimal
from typing import Optional, Union
from unittest.mock import patch

import sentry_sdk
from django.conf import settings
from django.core.cache import cache

from .logstash_logging.loggers import logstash_logger
from .metrics import (
    HISTOGRAM_BUCKET_MILLISECONDS,
    MetricHandler,
    _gauge_meter,
    _log_time,
    _metric_incr,
    _metric_reset,
    _summary_meter,
)
from .models import Log

nobitex_logger = logging.getLogger('nobitex')


def report_exception(**kwargs):
    if not settings.ENABLE_SENTRY:
        traceback.print_exception(*sys.exc_info())
        return
    return sentry_sdk.capture_exception()


def report_event(message, *, attach_stacktrace=False, **kwargs):
    if settings.METRICS_BACKEND == 'sentry':
        if not settings.ENABLE_SENTRY:
            return
        with sentry_sdk.push_scope() as scope:
            scope.update_from_kwargs(**kwargs)
            with patch.dict(sentry_sdk.Hub.current.client.options, {'attach_stacktrace': attach_stacktrace}):
                sentry_sdk.capture_message(message)
    else:
        print('[EVENT]', message, str(kwargs))


def log_event(message, level='', category='', module='', runner='', details=None):
    if settings.ONLY_REPLICA:
        return
    message = str(message)[:1000]
    if details:
        details = str(details)[:10000]
    if isinstance(level, str):
        try:
            level = getattr(Log.LEVEL_CHOICES, level.upper())
        except AttributeError:
            level = Log.LEVEL_CHOICES.NOTSET
    if isinstance(category, str):
        try:
            category = getattr(Log.CATEGORY_CHOICES, category)
        except AttributeError:
            category = Log.CATEGORY_CHOICES.general
    if isinstance(module, str):
        try:
            module = getattr(Log.MODULE_CHOICES, module)
        except AttributeError:
            module = Log.MODULE_CHOICES.general
    if isinstance(runner, str):
        try:
            runner = getattr(Log.RUNNER_CHOICES, runner)
        except AttributeError:
            runner = Log.RUNNER_CHOICES.generic
    if 'pytest' in sys.modules:
        print('[EVENTLOG]', message, details)
        return
    Log.objects.create(
        message=message,
        details=details,
        level=level,
        category=category,
        module=module,
        runner=runner,
    )


def get_metric_cache_key(metric: str, label_values: Optional[tuple]):
    """Return metric cache key with labels"""
    key = metric
    if label_values:
        normalized_label_values = (str(label_value).replace('_', '') for label_value in label_values)
        key += '__' + '_'.join(normalized_label_values)
    return key


def log_time(metric, time, labels: Optional[tuple] = None):
    """Log time for a metric, if redis handler is used, the avg time is stored."""
    metric_key = get_metric_cache_key(metric, labels)
    if MetricHandler.is_redis():
        cache_key = f'time_{metric_key}_avg'
        current_avg = cache.get(cache_key)
        avg = round((current_avg or time) * 0.2 + time * 0.8)
        if not current_avg or abs(avg - current_avg) >= 10:
            cache.set(cache_key, avg)
    if MetricHandler.is_kafka():
        try:
            _log_time(metric_key, time, buckets=HISTOGRAM_BUCKET_MILLISECONDS)
        except Exception as e:  # noqa: BLE001
            logstash_logger.info(
                'Error in log_time',
                extra={
                    'params': {'error': str(e), 'metric': metric, 'labels': str(labels)},
                    'index_name': 'metrics.migration',
                },
            )


def log_numerical_metric_avg(metric, number, labels: Optional[tuple] = None, change_scale: Decimal = Decimal(0.1)):
    """Log an average for a numerical metric"""
    metric_key = get_metric_cache_key(metric, labels)
    if MetricHandler.is_redis():
        cache_key = f'metric_{metric_key}_avg'
        current_avg = cache.get(cache_key)
        avg = round((current_avg or number) * 0.2 + number * 0.8)
        if not current_avg or abs(avg - current_avg) >= change_scale:
            cache.set(cache_key, avg)
    if MetricHandler.is_kafka():
        try:
            _summary_meter(metric_key, number)
        except Exception as e:  # noqa: BLE001
            logstash_logger.info(
                'Error in log_numerical_metric_avg',
                extra={
                    'params': {'error': str(e), 'metric': metric, 'labels': str(labels)},
                    'index_name': 'metrics.migration',
                },
            )


def log_time_without_avg(metric, time, labels: Optional[tuple] = None):
    """Log a time for a metric"""
    metric_key = get_metric_cache_key(metric, labels)
    if MetricHandler.is_redis():
        cache_key = f'time_{metric_key}_avg'
        cache.set(cache_key, time)
    if MetricHandler.is_kafka():
        try:
            _log_time(metric_key, time, buckets=HISTOGRAM_BUCKET_MILLISECONDS)
        except Exception as e:  # noqa: BLE001
            logstash_logger.info(
                'Error in log_time_without_avg',
                extra={
                    'params': {'error': str(e), 'metric': metric, 'labels': str(labels)},
                    'index_name': 'metrics.migration',
                },
            )


def metric_incr(metric: str, amount: int = 1, labels: Optional[tuple] = None):
    """ Log an event for a Counter metric """
    metric_key = get_metric_cache_key(metric, labels)
    if MetricHandler.is_redis():
        try:
            cache.incr(metric_key, amount)
        except ValueError:
            cache.set(metric_key, amount)
    if MetricHandler.is_kafka():
        try:
            _metric_incr(metric_key, amount)
        except Exception as e:  # noqa: BLE001
            logstash_logger.info(
                'Error in metric_incr',
                extra={
                    'params': {'error': str(e), 'metric': metric, 'labels': str(labels)},
                    'index_name': 'metrics.migration',
                },
            )


def metric_gauge(metric: str, value: Union[int, float], labels: Optional[tuple] = None):
    """Log an event for a Counter metric"""
    metric_key = get_metric_cache_key(metric, labels)
    if MetricHandler.is_redis():
        cache.set(metric_key, value)
    if MetricHandler.is_kafka():
        try:
            _gauge_meter(metric_key, value)
        except Exception as e:  # noqa: BLE001
            logstash_logger.info(
                'Error in metric_gauge',
                extra={
                    'params': {'error': str(e), 'metric': metric, 'labels': str(labels)},
                    'index_name': 'metrics.migration',
                },
            )


def metric_reset(metric: str, labels: Optional[tuple] = None):
    """ Resets a Counter metric to zero """
    metric_key = get_metric_cache_key(metric, labels)
    if MetricHandler.is_redis():
        try:
            cache.delete(metric_key)
        except Exception:  # noqa: BLE001
            report_exception()
    if MetricHandler.is_kafka():
        try:
            _metric_reset(metric_key)
        except Exception as e:  # noqa: BLE001
            logstash_logger.info(
                'Error in metric_reset',
                extra={
                    'params': {'error': str(e), 'metric': metric, 'labels': str(labels)},
                    'index_name': 'metrics.migration',
                },
            )


class BaseTimer:
    """Base timer class for use in more specialized timer classes.

        # TODO: Move main functionality of current Timer class to this class
    """
    timer = 0
    TIMERS = {}
