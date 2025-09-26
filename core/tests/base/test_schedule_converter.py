import pytest
from celery.schedules import crontab
from celery.schedules import schedule as cron_schedule
from django_cron import Schedule

from exchange.base.crons import ScheduleToCronConverter


def test_convert_to_celery_cron_with_run_at_times():
    schedule = Schedule(run_at_times=['10:30', '15:45'])

    result = ScheduleToCronConverter.convert_to_celery_cron(schedule)

    assert result == [
        crontab(minute=30, hour=10),
        crontab(minute=45, hour=15),
    ]


def test_convert_to_celery_cron_with_run_at_days_of_week():
    schedule = Schedule(run_on_days=[0, 3])
    result = ScheduleToCronConverter.convert_to_celery_cron(schedule)
    assert result == [
        crontab(minute=0, hour=0, day_of_week=0),
        crontab(minute=0, hour=0, day_of_week=3),
    ]

    schedule = Schedule(run_at_times=['10:30', '15:45'], run_on_days=[0, 3])
    result = ScheduleToCronConverter.convert_to_celery_cron(schedule)
    assert result == [
        crontab(minute=30, hour=10, day_of_week=0),
        crontab(minute=45, hour=15, day_of_week=0),
        crontab(minute=30, hour=10, day_of_week=3),
        crontab(minute=45, hour=15, day_of_week=3),
    ]


def test_convert_to_celery_cron_with_run_every_mins():
    schedule = Schedule(run_every_mins=30)
    result = ScheduleToCronConverter.convert_to_celery_cron(schedule)
    assert result == [cron_schedule(run_every=30 * 60)]


def test_convert_to_celery_cron_with_run_monthly_on_days():
    schedule = Schedule(run_monthly_on_days=[1, 15])
    result = ScheduleToCronConverter.convert_to_celery_cron(schedule)
    assert result == [
        crontab(minute=0, hour=0, day_of_month=1),
        crontab(minute=0, hour=0, day_of_month=15),
    ]

    schedule = Schedule(run_monthly_on_days=[1, 15], run_at_times=['08:00'])
    result = ScheduleToCronConverter.convert_to_celery_cron(schedule)
    assert result == [
        crontab(minute=0, hour=8, day_of_month=1),
        crontab(minute=0, hour=8, day_of_month=15),
    ]


def test_convert_to_celery_cron_with_all_combinations():
    schedule = Schedule(
        run_at_times=['09:00', '18:00'],
        run_on_days=[2, 5],
        run_monthly_on_days=[5, 25],
    )
    result = ScheduleToCronConverter.convert_to_celery_cron(schedule)
    assert result == [
        crontab(minute=0, hour=9, day_of_month=5, day_of_week=2),
        crontab(minute=0, hour=18, day_of_month=5, day_of_week=2),
        crontab(minute=0, hour=9, day_of_month=5, day_of_week=5),
        crontab(minute=0, hour=18, day_of_month=5, day_of_week=5),
        crontab(minute=0, hour=9, day_of_month=25, day_of_week=2),
        crontab(minute=0, hour=18, day_of_month=25, day_of_week=2),
        crontab(minute=0, hour=9, day_of_month=25, day_of_week=5),
        crontab(minute=0, hour=18, day_of_month=25, day_of_week=5),
    ]


def test_convert_to_celery_cron_run_every_with_others():
    for kwargs in [
        dict(run_at_times=['09:00', '18:00'], run_every_mins=30),
        dict(run_every_mins=30, run_on_days=[2, 5]),
        dict(run_every_mins=30, run_monthly_on_days=[5, 25]),
    ]:
        schedule = Schedule(**kwargs)
        with pytest.raises(ValueError, match='Combining run_every_mins and other args are not supported'):
            ScheduleToCronConverter.convert_to_celery_cron(schedule)
