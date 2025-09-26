import datetime
from decimal import Decimal
from typing import List, Optional, Union

from celery import shared_task
from celery.schedules import crontab, schedule
from django.conf import settings
from django.utils import timezone
from django.utils.functional import cached_property
from django_cron import CronJobBase, Schedule
from django_cron.backends.lock.cache import CacheLock
from django_cron.management.commands.runcrons import run_cron_with_cache_check
from django_cron.models import CronJobLog

from exchange.base.apimanager import APIManager
from exchange.base.calendar import ir_now
from exchange.base.decorators import measure_cron_execution
from exchange.base.helpers import deterministic_hash
from exchange.base.logging import report_exception
from exchange.base.models import AVAILABLE_CRYPTO_CURRENCIES, PRICE_PRECISIONS, Settings, get_currency_codename
from exchange.base.serializers import convert
from exchange.base.settings import NobitexSettings
from exchange.celery import app as celery_app


class CustomCronLock(CacheLock):
    """Customized Cron Locking Logic"""

    def lock(self):
        """
        This method sets a cache variable to mark current job as "already running".
        """
        if self.cache.get(self.lock_name):
            return False
        cron_class_name = (self.lock_name or '').split('.')[-1]
        timeout = (
            3 * 3600
            if cron_class_name in settings.LONG_RUNNING_CRONS
            else 12 * 3600
            if cron_class_name in settings.VERY_LONG_RUNNING_CRONS
            else self.timeout
        )
        self.cache.set(self.lock_name, timezone.now(), timeout)
        return True


class ScheduleToCronConverter:
    @staticmethod
    def convert_to_celery_cron(django_schedule: Schedule) -> List[crontab]:
        celery_cron_schedules = []

        if django_schedule.run_every_mins:
            if any((django_schedule.run_at_times, django_schedule.run_monthly_on_days, django_schedule.run_on_days)):
                raise ValueError('Combining run_every_mins and other args are not supported')

            run_every_mins = (
                django_schedule.run_every_mins
                if isinstance(django_schedule.run_every_mins, list)
                else [django_schedule.run_every_mins]
            )
            for run_every_min in run_every_mins:
                celery_cron_schedules.append(schedule(run_every=run_every_min * 60, app=celery_app))

            return celery_cron_schedules

        for day_of_month in django_schedule.run_monthly_on_days or ['*']:
            for day_of_week in django_schedule.run_on_days or ['*']:
                for time in django_schedule.run_at_times or ['0:0']:
                    hour, minute = map(int, time.split(':'))
                    celery_cron_schedules.append(
                        crontab(
                            minute=minute, hour=hour, day_of_month=day_of_month, day_of_week=day_of_week, app=celery_app
                        ),
                    )

        return celery_cron_schedules


class CronJob(CronJobBase):
    """
    A base class for defining cron jobs in a Django application.

    Attributes:
        schedule (Schedule): The schedule defining the execution frequency.
        code (str): A unique code for the cron job.
        celery_beat (bool): Indicates whether the cron job is scheduled via Celery Beat.
        task_name (str): The name of the Celery task, This arg is required for celery beat. Routing of the task will be determined by this.
        beat_schedule (Union[crontab, int]): The beat schedule for Celery Beat. Defaults to schedule.

    Example:

        >>> class FetchCurrencyValuesCron(CronJob):
        >>>     schedule = Schedule(run_every_mins=30)
        >>>     code = 'fetch_currency_values'
        >>>     celery_beat = True
        >>>     task_name = 'abc.core.liquidate
    """

    schedule: Schedule
    code = None
    celery_beat = False
    task_name = None
    beat_schedule: Union[crontab, int] = None

    @classmethod
    def module_name(cls):
        """Return module name of running cron class, used for reporting and metrics."""
        module_name = cls.__module__.split('.')
        if len(module_name) < 2:
            return 'other'
        return module_name[1]

    def set_process_title(self, status):
        if settings.IS_TEST_RUNNER:
            return
        try:
            from setproctitle import setproctitle
        except ImportError:
            return
        setproctitle(f'runcrons - {self.module_name()} - {self.code} - {status}')

    def do(self):
        try:
            self.set_process_title('running')
            with measure_cron_execution(
                app=convert(self.module_name(), convert_to_camelcase=True),
                cron=self.__class__.__name__,
            ):
                self.run()
            self.set_process_title('done')
        except Exception:
            report_exception()
            raise

    def run(self):
        raise NotImplementedError

    @cached_property
    def last_successful_start(self) -> Optional[datetime.datetime]:
        """Get start time of last successful cron

        Since django_cron prev_success_cron if filled after cron execution,
        it cannot be used during cron jobs
        """
        try:
            return CronJobLog.objects.filter(code=self.code, is_success=True).latest('start_time').start_time
        except CronJobLog.DoesNotExist:
            if self.schedule.run_every_mins:
                return ir_now() - datetime.timedelta(minutes=self.schedule.run_every_mins)

    @classmethod
    def get_beat_name(cls, beat_schedule: Union[crontab, int]):
        postfix = ''
        if isinstance(beat_schedule, crontab):
            postfix = '_' + str(deterministic_hash(str(beat_schedule).encode()))[:4]

        name = f'{cls.code}{postfix}'
        if cls.code.startswith(cls.module_name()):
            return name

        return f'{cls.module_name()}_{name}'

    @classmethod
    def get_beat_task(cls):
        @shared_task(name=cls.task_name)
        def run_cron():
            run_cron_with_cache_check(cls, force=True)

        return run_cron

    @classmethod
    def get_beat_schedules(cls):
        return cls.beat_schedule or ScheduleToCronConverter.convert_to_celery_cron(cls.schedule)

    @classmethod
    def register_beat_crons(cls):
        for cron in cls.__subclasses__():
            if cron.celery_beat and cron.schedule:
                beat_schedules = cron.get_beat_schedules()
                if not isinstance(beat_schedules, list):
                    beat_schedules = [beat_schedules]

                if not cron.task_name:
                    raise ValueError('task_name is required when celery_beat is True')

                for beat_schedule in beat_schedules:
                    celery_app.add_periodic_task(
                        beat_schedule,
                        cron.get_beat_task(),
                        name=cron.get_beat_name(beat_schedule),
                    )


class FetchCurrencyValuesCron(CronJob):
    schedule = Schedule(run_every_mins=30)
    code = 'fetch_currency_values'

    def run(self):
        for currency in AVAILABLE_CRYPTO_CURRENCIES:
            currency_codename = get_currency_codename(currency)
            value = NobitexSettings.get_binance_price(currency)
            if value is None:
                continue
            value = Decimal(value).quantize(
                PRICE_PRECISIONS.get('{}USDT'.format(currency_codename.upper()), Decimal('1e-2'))
            )
            Settings.set('value_{}_usd'.format(currency_codename), str(value))


class ResetAPILimitsCron(CronJob):
    schedule = Schedule(run_at_times=['00:00', '16:00', '17:00', '18:00', '19:00'])
    code = 'reset_api_limits'

    def run(self):
        APIManager.reset_calls_count('finnotech', endpoint='nidVerification')
