import datetime
from datetime import timedelta
import jdatetime
from django.utils import timezone
from decimal import Decimal
from django.db.models import Q, Sum
import pytz
from exchange.accounts.models import Confirmed
from exchange.base.calendar import ir_now
from exchange.base.models import RIAL
from exchange.portfolio.models import UserTotalMonthlyProfit, UserTotalDailyProfit
from exchange.shetab.models import ShetabDeposit
from exchange.wallet.models import WithdrawRequest, ConfirmedWalletDeposit, BankDeposit


def apply_withdraw_deposit(first_balance, last_balance, withdraw, deposit):
    """ apply withdraw and deposits on first balance and last balance
    """
    last_balance += withdraw
    first_balance += deposit
    return first_balance, last_balance


def calc_profit(cost, revenue):
    revenue = revenue if revenue >= 0 else 0
    if cost > 0:
        net_profit = revenue - cost
        net_profit_percentage = (net_profit / cost) * 100
        return {
            'profit': net_profit,
            'percentage': net_profit_percentage
        }
    return {
        'profit': 0,
        'percentage': 0
    }


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
        return timezone.make_aware(
            timezone.datetime.combine(date_time, timezone.datetime.max.time()) - timezone.timedelta(hours=1)
        )


def get_last_day_of_month_jalali(jalali_report_date):
    next_month = jalali_report_date.replace(day=28) + jdatetime.timedelta(days=4)
    last_day = (next_month.replace(day=1) - jdatetime.timedelta(days=1)).day
    return last_day


def get_total_withdraw(user, report_date, from_date=None):

    # get withdrawals of user in status (accepted, sent, done and manual_accepted)
    status_filter = Q(wallet__user=user, status__in=[3, 4, 5, 10])

    confirmation_delay = timedelta(hours=2)
    if from_date:
        from_date = get_earliest_time(from_date)
    else:
        from_date = get_earliest_time(report_date)
    report_date = get_latest_time(report_date)

    # This filter is for improving performance only
    date_filter = Q(created_at__gte=from_date - confirmation_delay) & Q(created_at__lt=report_date)
    transaction_date_filter = Q(transaction__created_at__gte=from_date) & Q(transaction__created_at__lt=report_date)

    withdraws = WithdrawRequest.objects.filter(
        status_filter, date_filter,
    ).filter(transaction_date_filter).values('rial_value')

    total_withdraw = withdraws.aggregate(sum=Sum('rial_value'))['sum'] or Decimal('0')
    return total_withdraw


def get_total_deposits(user, report_date, from_date=None):
    shetab_status_filter = Q(user=user, status_code=ShetabDeposit.STATUS.pay_success)
    bank_status_filter = Q(user=user, confirmed=True, status=Confirmed.STATUS.confirmed)

    confirmation_delay = timedelta(hours=3)
    if from_date:
        from_date = get_earliest_time(from_date)
    else:
        from_date = get_earliest_time(report_date)
    report_date = get_latest_time(report_date)

    # This filter is for improving performance only
    date_filter = Q(created_at__gte=from_date - confirmation_delay) & Q(created_at__lt=report_date)
    transaction_filter = Q(transaction__created_at__gte=from_date, transaction__created_at__lt=report_date)

    confirmed_wallet_deposits = ConfirmedWalletDeposit.objects.filter(
        date_filter,
        _wallet__user=user,
        confirmed=True,
        validated=True,
    ).filter(transaction_filter).exclude(_wallet__currency=RIAL).values('rial_value')

    shetab_deposits = ShetabDeposit.objects.filter(
        shetab_status_filter, date_filter,
    ).filter(transaction_filter).values('amount')

    bank_deposits = BankDeposit.objects.filter(
        bank_status_filter, date_filter,
    ).filter(transaction_filter).values('amount')

    total_confirmed_deposit = confirmed_wallet_deposits.aggregate(sum=Sum('rial_value'))['sum'] or Decimal('0')
    total_shetab_deposit = shetab_deposits.aggregate(sum=Sum('amount'))['sum'] or Decimal('0')
    total_bank_deposit = bank_deposits.aggregate(sum=Sum('amount'))['sum'] or Decimal('0')

    total_deposit = total_confirmed_deposit + total_shetab_deposit + total_bank_deposit
    return total_deposit


def get_total_saved_withdraw(user, report_date, from_date=None):
    """Calculate and return the sum of total_withdraw values that saved in UserTotal(Daily/Monthly)Profit model.
    total_withdraw is a Rial value
    """
    from_date = get_earliest_time(from_date) if from_date else get_earliest_time(report_date)
    to_date = get_latest_time(report_date)

    first_daily_profit = UserTotalDailyProfit.objects.filter(user=user).order_by('report_date').first()
    first_daily_report_date = get_earliest_time(first_daily_profit.report_date) if first_daily_profit\
        else ir_now() - timedelta(days=90)

    if from_date >= first_daily_report_date:
        total_withdraw = UserTotalDailyProfit.objects.filter(user=user,
                                                             report_date__gte=from_date,
                                                             report_date__lte=to_date) \
                                             .aggregate(sum=Sum('total_withdraw'))['sum'] or Decimal('0')
        return total_withdraw
    monthly_qs = UserTotalMonthlyProfit.objects.filter(user=user,
                                                       report_date__gte=from_date,
                                                       report_date__lte=first_daily_report_date).order_by('report_date')
    total_withdraw_monthly = 0
    from_date_daily = from_date
    if monthly_qs:
        last_date = jdatetime.datetime.fromgregorian(date=monthly_qs.last().report_date)
        last_day_of_last_date = get_last_day_of_month_jalali(last_date)
        from_date_daily = get_earliest_time((last_date.replace(day=last_day_of_last_date) + timedelta(days=1))
                                            .togregorian())
        total_withdraw_monthly = monthly_qs.aggregate(sum=Sum('total_withdraw'))['sum'] or Decimal('0')

    total_withdraw_daily = UserTotalDailyProfit.objects.filter(user=user,
                                                               report_date__gte=from_date_daily,
                                                               report_date__lte=to_date) \
                                               .aggregate(sum=Sum('total_withdraw'))['sum'] or Decimal('0')

    total_withdraw = total_withdraw_monthly + total_withdraw_daily
    return total_withdraw


def get_total_saved_deposits(user, report_date, from_date=None):
    """Calculate and return the sum of total_deposit values that saved in UserTotal(Daily/Monthly)Profit model.
    total_deposit is a Rial value
    """
    from_date = get_earliest_time(from_date) if from_date else get_earliest_time(report_date)
    to_date = get_latest_time(report_date)

    first_daily_profit = UserTotalDailyProfit.objects.filter(user=user).order_by('report_date').first()
    first_daily_report_date = get_earliest_time(first_daily_profit.report_date) if first_daily_profit\
        else ir_now() - timedelta(days=90)

    if from_date >= first_daily_report_date:
        total_deposit = UserTotalDailyProfit.objects.filter(user=user,
                                                            report_date__gte=from_date,
                                                            report_date__lte=to_date)\
            .aggregate(sum=Sum('total_deposit'))['sum'] or Decimal('0')
        return total_deposit

    monthly_qs = UserTotalMonthlyProfit.objects.filter(user=user,
                                                       report_date__gte=from_date,
                                                       report_date__lte=first_daily_report_date).order_by('report_date')
    from_date_daily = from_date
    total_deposit_monthly = 0
    if monthly_qs:
        total_deposit_monthly = monthly_qs.aggregate(sum=Sum('total_deposit'))['sum'] or Decimal('0')

        last_date = jdatetime.datetime.fromgregorian(date=monthly_qs.last().report_date)
        last_day_of_last_date = get_last_day_of_month_jalali(last_date)
        from_date_daily = get_earliest_time((last_date.replace(day=last_day_of_last_date) + timedelta(days=1))
                                            .togregorian())

    total_deposit_daily = UserTotalDailyProfit.objects.filter(user=user,
                                                              report_date__gte=from_date_daily,
                                                              report_date__lte=to_date) \
                                              .aggregate(sum=Sum('total_deposit'))['sum'] or Decimal('0')

    total_deposit = total_deposit_monthly + total_deposit_daily
    return total_deposit


def calc_daily_profit_until(report_date, user):
    first_balance = UserTotalMonthlyProfit.objects.filter(user=user).order_by('report_date').first()
    user_daily = UserTotalDailyProfit.objects.filter(user=user).order_by('report_date')

    if first_balance:
        first_total_balance = first_balance.first_day_total_balance
    else:
        first_balance = user_daily.first()
        first_total_balance = first_balance.total_balance if first_balance else 0

    last_balance = user_daily.filter(report_date__lte=report_date.date()).order_by('report_date').last()

    if not (first_balance and last_balance):
        return {
            'profit': 0,
            'percentage': 0
        }

    total_withdraw = get_total_withdraw(user, report_date, first_balance.report_date)
    total_deposit = get_total_deposits(user, report_date, first_balance.report_date)
    first_total_balance, last_total_balance = apply_withdraw_deposit(first_total_balance,
                                                                     last_balance.total_balance,
                                                                     total_withdraw,
                                                                     total_deposit)
    return calc_profit(first_total_balance, last_total_balance)


def get_withdraws_in_range(from_date, to_date):
    from_date = get_earliest_time(from_date)
    report_date = get_latest_time(to_date)
    half_hour = timedelta(minutes=30)
    status_filter = Q(status__in=[
        WithdrawRequest.STATUS.accepted,
        WithdrawRequest.STATUS.sent,
        WithdrawRequest.STATUS.done,
        WithdrawRequest.STATUS.manual_accepted,
    ])
    date_filter = Q(created_at__gte=from_date - half_hour) & Q(created_at__lte=report_date)
    transaction_date_filter = Q(transaction__created_at__gte=from_date) & Q(transaction__created_at__lte=report_date)

    withdraws = WithdrawRequest.objects.filter(
        status_filter,
        date_filter).filter(
        transaction_date_filter
    ).values('wallet__user', 'transaction__created_at__date').annotate(
        sum=Sum('rial_value')
    )

    return {
        f"{withdraw['transaction__created_at__date']}_{withdraw['wallet__user']}": withdraw['sum'] if withdraw['sum'] else 0
        for withdraw in withdraws
    }


def get_deposits_in_range(from_date, to_date):
    from_date = get_earliest_time(from_date)
    report_date = get_latest_time(to_date)
    half_hour = timedelta(minutes=30)
    shetab_status_filter = Q(status_code=ShetabDeposit.STATUS.pay_success)
    bank_status_filter = Q(confirmed=True, status=Confirmed.STATUS.confirmed)

    date_filter = Q(created_at__gte=from_date - half_hour) & Q(created_at__lte=report_date)
    transaction_filter = Q(transaction__created_at__gte=from_date, transaction__created_at__lte=report_date)

    confirmed_wallet_deposits = ConfirmedWalletDeposit.objects.filter(
        date_filter,
        confirmed=True,
        validated=True,
    ).filter(transaction_filter).exclude(_wallet__currency=RIAL).values('_wallet__user', 'transaction__created_at__date')\
        .annotate(sum=Sum('rial_value'))
    shetab_deposits = ShetabDeposit.objects.filter(shetab_status_filter, date_filter).filter(transaction_filter).\
        values('user', 'transaction__created_at__date').annotate(sum=Sum('amount'))
    bank_deposits = BankDeposit.objects.filter(bank_status_filter, date_filter).filter(transaction_filter).\
        values('user', 'transaction__created_at__date').annotate(sum=Sum('amount'))

    deposits = {}
    for confirmed_wallet_deposit in confirmed_wallet_deposits:
        confirmed_deposit_key = f"{confirmed_wallet_deposit['transaction__created_at__date']}_{confirmed_wallet_deposit['wallet__user']}"
        deposits[confirmed_deposit_key] = confirmed_wallet_deposit['sum'] or 0
    for shetab_deposit in shetab_deposits:
        shetab_deposit_key = f"{shetab_deposit['transaction__created_at__date']}_{shetab_deposit['user']}"
        if shetab_deposit_key in deposits.keys():
            deposits[shetab_deposit_key] += shetab_deposit['sum']
        else:
            deposits[shetab_deposit_key] = shetab_deposit['sum'] or 0
    for bank_deposit in bank_deposits:
        bank_deposit_key = f"{bank_deposit['transaction__created_at__date']}_{bank_deposit['user']}"
        if bank_deposit_key in deposits.keys():
            deposits[bank_deposit_key] += bank_deposit['sum']
        else:
            deposits[bank_deposit_key] = bank_deposit['sum'] or 0

    return deposits


def get_total_cached_data(data, user_id, from_date, to_date):
    """ Data is a dictionary that contains withdraws or deposits in from_date and to_date range
    with report_date + underline + user_id like this : 2021-01-01_45465
    """
    total_amount = 0
    from_date = from_date.date() if isinstance(from_date, datetime.datetime) else from_date
    to_date = to_date.date() if isinstance(to_date, datetime.datetime) else to_date
    filtered_data = {k: v for k, v in data.items() if k.endswith(str(user_id))}
    for key, amount in filtered_data.items():
        rdate, item_user_id = key.split('_')
        report_date = datetime.datetime.strptime(rdate, '%Y-%m-%d').date()
        if from_date <= report_date <= to_date:
            total_amount += amount
    return total_amount
