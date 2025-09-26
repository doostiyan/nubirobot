import jdatetime
from django.utils import timezone
import datetime
from exchange.base import calendar
from exchange.base.calendar import get_start_and_end_of_jalali_week


def test_to_shamsi_date():
    dt = timezone.datetime(2016, 11, 18, 13, 34, 42)
    assert calendar.to_shamsi_date(dt) == '1395/08/28 13:34:42'
    assert calendar.to_shamsi_date(dt.date()) == '1395/08/28'
    assert calendar.to_shamsi_date(dt, '%Y-%m-%dT%H:%M:%S') == '1395-08-28T13:34:42'
    assert calendar.to_shamsi_date(dt, '%Y%m%d') == '13950828'


def test_parse_shamsi_date():
    dt = calendar.parse_shamsi_date('1395-08-28')
    assert dt.year == 2016 and dt.month == 11 and dt.day == 18
    assert not dt.hour and not dt.minute and not dt.second
    assert dt.tzinfo.tzname(dt) == '+0330'
    assert calendar.parse_shamsi_date('1395-08-28 13:34:42') == dt
    dt = calendar.parse_shamsi_date('1395/08/28 13:34:42', '%Y/%m/%d %H:%M:%S')
    assert dt.year == 2016 and dt.month == 11 and dt.day == 18
    assert dt.hour == 13 and dt.minute == 34 and dt.second == 42
    assert dt.tzinfo.tzname(dt) == '+0330'


def test_start_and_end_of_jalali_datetime():
    date_ = datetime.datetime(year=2024, month=10, day=21)
    expected_start_of_week = datetime.datetime(year=2024, month=10, day=19)
    expected_end_of_week = datetime.datetime(year=2024, month=10, day=25,hour=23, minute=59, second=59)
    expected_jalali_start_of_week = jdatetime.datetime.fromgregorian(datetime=expected_start_of_week)
    expected_jalali_end_of_week = jdatetime.datetime.fromgregorian(datetime=expected_end_of_week)

    actual_start, actual_end = get_start_and_end_of_jalali_week(date_)

    assert expected_start_of_week == actual_start.togregorian()
    assert expected_end_of_week == actual_end.togregorian()
    assert expected_jalali_start_of_week == actual_start
    assert expected_jalali_end_of_week == actual_end
