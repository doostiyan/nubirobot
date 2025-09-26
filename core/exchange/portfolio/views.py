import datetime

from exchange.base.api import api
from exchange.base.calendar import ir_now, ir_today
from exchange.base.constants import ZERO
from exchange.base.parsers import parse_bool, parse_date
from exchange.features.utils import require_feature
from exchange.portfolio.functions import (
    apply_withdraw_deposit,
    calc_daily_profit_until,
    calc_profit,
    get_total_saved_deposits,
    get_total_saved_withdraw,
)
from exchange.portfolio.models import UserTotalDailyProfit


@api
@require_feature('portfolio')
def last_week_daily_profit(request):
    """
        List daily total profit of user in last 7 days or 30 days by -monthly- parameter
        return last 30 day data if monthly post with true value
    """
    is_monthly = parse_bool(request.g('monthly'))
    report_day_count = 30 if is_monthly else 7
    today = ir_today()
    user_total_profit_daily = UserTotalDailyProfit.objects.filter(
        user=request.user,
        report_date__lte=today - datetime.timedelta(days=1),
        report_date__gte=today - datetime.timedelta(days=report_day_count)
    ).order_by('report_date').values(
        'report_date',
        'profit',
        'profit_percentage',
        'total_balance',
    )
    user_total_profit_daily = {item['report_date']: item for item in user_total_profit_daily}
    result = []
    for i in range(report_day_count, 0, -1):
        report_date = today - datetime.timedelta(days=i)
        day_profit = user_total_profit_daily.get(report_date, {})
        data = {
            'report_date': report_date,
            'total_profit': day_profit.get('profit', '0'),
            'total_profit_percentage': day_profit.get('profit_percentage', '0'),
            'total_balance': day_profit.get('total_balance', '0'),
        }
        result.append(data)

    if not result:
        return {
            'status': 'failed',
            'code': 'LastWeekDailyProfitFail',
            'message': 'اطلاعاتی جهت نمایش وجود ندارد'
        }
    return {
        'status': 'ok',
        'data': result
    }


@api
@require_feature('portfolio')
def last_week_daily_total_profit(request):
    """
        List daily total profits from first of user orders in last 7 or 30 days by -monthly- parameter
        return last 30 day data if monthly post with true value
    """
    is_monthly = parse_bool(request.g('monthly'))
    report_day_count = 30 if is_monthly else 7

    final_data = []
    try:
        for i in range(report_day_count, 0, -1):
            report_date = ir_now().replace(hour=23, minute=59, second=59) - datetime.timedelta(days=i)
            total_data = calc_daily_profit_until(report_date, request.user)
            data = {
                'report_date': report_date.date(),
                'total_profit': total_data['profit'] or '0',
                'total_profit_percentage': total_data['percentage'] or '0'
            }
            final_data.append(data)
    except ValueError as e:
        return {
            'status': 'failed',
            'code': 'LastWeekDailyTotalProfitFail',
            'message': str(e)
        }
    if not final_data:
        return {
            'status': 'failed',
            'code': 'LastWeekDailyTotalProfitFail',
            'message': 'اطلاعاتی جهت نمایش وجود ندارد'
        }
    return {
        'status': 'ok',
        'data': final_data
    }


@api
@require_feature('portfolio')
def last_month_total_profit(request):
    """
        total profit of user orders in last 30 days
    """
    user = request.user
    to_date = ir_today()
    from_date = to_date - datetime.timedelta(days=30)
    total_data = UserTotalDailyProfit.objects \
        .filter(user=user, report_date__gte=from_date, report_date__lte=to_date).order_by('report_date')
    first_data = total_data.first()
    last_data = total_data.last()
    if not (first_data and last_data):
        return {
            'status': 'failed',
            'code': 'LastMonthTotalProfitFail',
            'message': 'اطلاعاتی جهت نمایش وجود ندارد'
        }
    first_balance = first_data.total_balance

    total_withdraw = get_total_saved_withdraw(user, last_data.report_date, first_data.report_date)
    total_deposit = get_total_saved_deposits(user, last_data.report_date, first_data.report_date)
    first_balance, last_balance = apply_withdraw_deposit(first_balance,
                                                         last_data.total_balance,
                                                         total_withdraw,
                                                         total_deposit)
    profits = calc_profit(first_balance, last_balance)
    return {
        'status': 'ok',
        'data': {
            'total_profit': profits['profit'] if profits else '0',
            'total_profit_percentage': profits['percentage'] if profits else '0'
        }
    }


@api
@require_feature('portfolio')
def get_daily_total_balance(request):
    report_date = parse_date(request.g('date')) or ir_today() - datetime.timedelta(days=1)
    user_daily_profit = UserTotalDailyProfit.objects.filter(user=request.user, report_date=report_date).first()
    total_balance = user_daily_profit.total_balance if user_daily_profit else ZERO
    return {
        'status': 'ok',
        'data': {
            'total_balance': total_balance
        }
    }
