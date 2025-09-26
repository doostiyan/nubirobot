import datetime
import re
from datetime import date
from typing import Tuple, Union

import jdatetime
import pytz
from django.utils import timezone
from jdatetime import GregorianToJalali
from jdatetime import date as jdate

ir_dst = pytz.timezone('Asia/Tehran')

MONTH_CHOICES_FARSI = {
    1: 'فروردین',
    2: 'اردیبهشت',
    3: 'خرداد',
    4: 'تیر',
    5: 'مرداد',
    6: 'شهریور',
    7: 'مهر',
    8: 'آبان',
    9: 'آذر',
    10: 'دی',
    11: 'بهمن',
    12: 'اسفند',
}


def ir_now():
    """ Return current time as a timezone aware datetime in Iran timezone

        The server environment may have a different timezone so it should not
          be assumed that every returned datetime is in Iran timezone. This
          method is especially useful when directly using field of datetimes,
          like checking hour and minute.
    """
    return timezone.now().astimezone(ir_tz())


def ir_today():
    return ir_now().date()


def parse_shamsi_date(shamsi_date_str, format_=None):
    """ Parses a date string like '1395-09-16' and return a python datetime object
          containing the miladi equivalent of that date (timezone aware)

        :param str shamsi_date_str: '1395-09-16'
        :param str format_: '%Y-%m-%d'
        :return datetime.datetime: timezone aware datetime object
    """
    if not shamsi_date_str:
        return None
    default_format = '%Y-%m-%d'
    if not format_:  # Support breaking changes in jdatetime 3.8.2
        result = re.findall(r'\d+-\d+-\d+', shamsi_date_str)
        if result:
            shamsi_date_str = result[0]
    try:
        dt = jdatetime.datetime.strptime(shamsi_date_str, format_ or default_format).togregorian()
        return ir_dst.localize(dt)
    except:
        raise ValueError('Invalid shamsi date: ' + shamsi_date_str)


def to_shamsi_date(dt, format_=None):
    """ Returns the standard shamsi representation of a python date object.
         Result will be in '1396-09-16' format.
    """
    default_format = '%Y/%m/%d'
    if isinstance(dt, datetime.datetime):
        dt = dt.astimezone(ir_dst)
        default_format += ' %H:%M:%S'
    return jdatetime.datetime.fromgregorian(datetime=dt).strftime(format_ or default_format)


def get_readable_date_str(dt):
    """ Human readable string (e.g. ۱۸ دی) for the given datetime

        :type dt: datetime.datetime
        :return str:
    """
    is_datetime = isinstance(dt, datetime.datetime)
    if is_datetime:
        dt = dt.astimezone(ir_dst)
    shamsi_date = GregorianToJalali(dt.year, dt.month, dt.day)
    return '{} {} {}'.format(
        shamsi_date.jday,
        jdate.j_months_fa[shamsi_date.jmonth - 1],
        shamsi_date.jyear % 100,
    )


def get_readable_weekday_str(dt):
    """ Human readable string (e.g. شنبه ۱۸ دی) for the given datetime

        :type dt: datetime.datetime
        :return str:
    """
    is_datetime = isinstance(dt, datetime.datetime)
    if is_datetime:
        dt = dt.astimezone(ir_dst)
    weekday = dt.weekday()
    WEEKDAY_CHOICES = {
        0: ('دوشنبه'), 1: ('سه‌شنبه'), 2: ('چهارشنبه'), 3: ('پنج‌شنبه'),
        4: ('جمعه'), 5: ('شنبه'), 6: ('یکشنبه')
    }
    shamsi_date = GregorianToJalali(dt.year, dt.month, dt.day)
    now = datetime.datetime.now().date()
    year_now = GregorianToJalali(now.year, now.month, now.day).jyear
    year = shamsi_date.jyear if year_now != shamsi_date.jyear else ''
    return '{} {} {} {}'.format(
        WEEKDAY_CHOICES[weekday],
        shamsi_date.jday,
        jdate.j_months_fa[shamsi_date.jmonth - 1],
        year,
    )


def as_ir_tz(d):
    return d.astimezone(ir_tz())


def ir_tz():
    return ir_dst


def time_diff_minutes(dt_from, dt_to=None):
    dt_to = ir_now() if not dt_to else dt_to
    diff = dt_to - dt_from
    minutes = diff.days * 24 * 60 + diff.seconds // 60
    return minutes


def jalali_format(date, mode=None):
    if mode is None:
        if isinstance(date, datetime.datetime):
            mode = 'datetime'
        elif isinstance(date, datetime.date):
            mode = 'date'
        else:
            mode = 'full_datetime'
    date_type_list = ['date', 'datetime', 'full_datetime', 'full_date', 'weekday']
    if not date or not mode in date_type_list:
        return '-'
    MONTHS_CHOICES = {
        '01': ('فروردین'), '02': ('اردیبهشت'), '03': ('خرداد'), '04': ('تیر'),
        '05': ('مرداد'), '06': ('شهریور'), '07': ('مهر'), '08': ('آبان'),
        '09': ('آذر'), '10': ('دی'), '11': ('بهمن'), '12': ('اسفند')
    }
    jalali = to_shamsi_date(date)
    if mode == 'weekday':
        return get_readable_weekday_str(date)
    if mode == 'full_datetime':
        return jalali
    if mode == 'full_date':
        return jalali.split()[0]
    if mode == 'date':
        jalali_date = jalali.split()[0]
        jalali_date_now = to_shamsi_date(datetime.datetime.now().date())
        time = ''
    else:
        jalali_date, time = jalali.split()
        jalali_date_now = to_shamsi_date(datetime.datetime.now()).split()[0]
    if jalali_date == jalali_date_now:
        return time
    year, month, day = jalali_date.split('/')
    year_now = jalali_date_now.split('/')[0]
    if year == year_now:
        mon = MONTHS_CHOICES[month]
        jalali = day + ' ' + mon + ' ' + time
    return jalali


def timedelta_format(value):
    if value.seconds < 1:
        return '1 >'
    if value.seconds < 60:
        return f'{value.seconds} ثانیه'
    if value.seconds < 3600:
        return f'{value.seconds // 60}:{value.seconds % 60:0>2}'
    return str(value).split('.')[0].replace('days', 'روز').replace('day', 'روز')


class DateTimeHelper:

    @classmethod
    def to_jalali_str(cls, value: Union[jdatetime.datetime, datetime.datetime], format_: str = "%a, %d %b %Y %H:%M:%S"):
        """Convert a datetime object to equivalent jalali string representation"""
        jdatetime.set_locale('fa_IR')
        if isinstance(value, jdatetime.datetime):
            return value.strftime(format_)
        return jdatetime.datetime.fromgregorian(datetime=value).strftime(format_)

    @classmethod
    def to_gregorian_str(cls, value, format_="%a, %d %b %Y %H:%M:%S"):
        """Convert a datetime object to equivalent gregorian string representation"""
        return value.strftime(format_)


def get_earliest_time(date_time):
    try:
        return timezone.make_aware(timezone.datetime.combine(date_time, timezone.datetime.min.time()))
    except pytz.NonExistentTimeError:
        return timezone.make_aware(
            timezone.datetime.combine(date_time, timezone.datetime.min.time()) + timezone.timedelta(hours=1)
        )


def get_latest_time(date_time):
    try:
        return timezone.make_aware(timezone.datetime.combine(date_time, timezone.datetime.max.time()))
    except pytz.AmbiguousTimeError:
        return timezone.make_aware(timezone.datetime.combine(date_time, timezone.datetime.max.time()), is_dst=False)


def get_first_and_last_of_jalali_month(date_: date) -> Tuple[date, date]:
    """Return first and last of the shamsi(jalali) month in gregorian

    Returns:
        Tuple[datetime.date, datetime.date]: first and last date of month
    """
    first_of_month_jalali, last_of_month_jalali = get_jalali_first_and_last_of_jalali_month(date_)
    first_of_month = first_of_month_jalali.togregorian()
    last_of_month = last_of_month_jalali.togregorian()
    return first_of_month, last_of_month


def get_jalali_first_and_last_of_jalali_month(
    date_: date,
) -> Tuple[jdatetime.date, jdatetime.date]:
    """Return first and last of the shamsi(jalali) month in jalali

    Returns:
        Tuple[jdatetime.date, jdatetime.date]: first and last date of month in jalali
    """
    jalali_date = jdatetime.date.fromgregorian(date=date_)
    first_of_month_jalali = jalali_date.replace(day=1)
    last_of_month_jalali = (first_of_month_jalali + jdatetime.timedelta(days=31)).replace(day=1) - jdatetime.timedelta(
        days=1
    )
    return first_of_month_jalali, last_of_month_jalali


def get_start_and_end_of_jalali_week(date_: date) -> Tuple[jdatetime.datetime, jdatetime.datetime]:
    jalali_date = jdatetime.date.fromgregorian(date=date_)
    jalali_datetime = jdatetime.datetime(year=jalali_date.year, month=jalali_date.month, day=jalali_date.day)
    start_of_week = jalali_datetime - datetime.timedelta(days=jalali_datetime.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + datetime.timedelta(days=6)
    end_of_week = end_of_week.replace(hour=23, minute=59, second=59)

    return start_of_week, end_of_week
