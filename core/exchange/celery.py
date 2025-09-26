import os
import time

from cachetools import TTLCache, cached
from celery import Celery as CeleryBase
from celery import Task as CeleryTask

from exchange.base.metrics import _gauge_meter_incr, _log_time, _metric_incr


class Celery(CeleryBase):
    def get_queue_len(self, queue):
        """Return the number of tasks in the given queue

        Based on https://stackoverflow.com/q/18631669/462865
        """
        with self.connection_or_acquire() as conn:
            return conn.default_channel.client.llen(queue)


class Task(CeleryTask):
    """
    A base task class that extends celery Task to add custom timing and metric logging functionality.
    """

    _settings = None
    running_tasks_metric_key = 'celery_running_tasks'
    celery_task_total_metric_key = 'celery_task_total'
    celery_task_duration_seconds_metric_key = 'celery_task_duration_seconds'

    @property
    @cached(cache=TTLCache(maxsize=1, ttl=60), key=lambda self: ('is_celery_monitoring_enabled', Task))
    def is_celery_monitoring_enabled(self):
        if self._settings is None:
            from exchange.base.models import Settings

            self.__class__._settings = Settings

        return self._settings.get_value('is_enabled_celery_monitoring', default='false').strip().lower() == 'true'

    @property
    @cached(cache=TTLCache(maxsize=1, ttl=60), key=lambda self: ('celery_monitoring_sample_rate', Task))
    def celery_monitoring_sample_rate(self):
        if self._settings is None:
            from exchange.base.models import Settings

            self.__class__._settings = Settings

        return self._settings.get_float('celery_monitoring_sample_rate', default='1')

    @property
    @cached(cache=TTLCache(maxsize=1, ttl=60), key=lambda self: ('is_running_monitoring_enabled', Task))
    def is_running_monitoring_enabled(self):
        if self._settings is None:
            from exchange.base.models import Settings

            self.__class__._settings = Settings

        return (
            self._settings.get_value('is_enabled_celery_running_monitoring', default='false').strip().lower() == 'true'
        )

    def before_start(self, task_id, args, kwargs):
        if self.is_celery_monitoring_enabled:
            self._start_time = time.time()

            if self.is_running_monitoring_enabled:
                _gauge_meter_incr(self.running_tasks_metric_key, amount=1, task_name=self.name)

        super().before_start(task_id, args, kwargs)

    def on_success(self, retval, task_id, args, kwargs):
        if self.is_celery_monitoring_enabled:
            duration = time.time() - self._start_time
            _log_time(
                self.celery_task_duration_seconds_metric_key,
                value=duration,
                sample_rate=self.celery_monitoring_sample_rate,
                task_name=self.name,
            )
            _metric_incr(
                self.celery_task_total_metric_key,
                sample_rate=self.celery_monitoring_sample_rate,
                task_name=self.name,
                status='success',
            )
        super().on_success(retval, task_id, args, kwargs)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        if self.is_celery_monitoring_enabled:
            _metric_incr(
                self.celery_task_total_metric_key,
                sample_rate=self.celery_monitoring_sample_rate,
                task_name=self.name,
                status='failure',
            )
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        if self.is_celery_monitoring_enabled:
            _metric_incr(
                self.celery_task_total_metric_key,
                sample_rate=self.celery_monitoring_sample_rate,
                task_name=self.name,
                status='retry',
            )
            if self.is_running_monitoring_enabled:
                _gauge_meter_incr(self.running_tasks_metric_key, amount=-1, task_name=self.name)

        super().on_retry(exc, task_id, args, kwargs, einfo)

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        if self.is_celery_monitoring_enabled and self.is_running_monitoring_enabled:
            _gauge_meter_incr(self.running_tasks_metric_key, amount=-1, task_name=self.name)

        return super().after_return(status, retval, task_id, args, kwargs, einfo)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'exchange.settings')

app = Celery('exchange', task_cls=Task)
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
