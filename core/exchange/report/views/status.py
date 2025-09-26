import datetime

from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Q
from django.shortcuts import render
from django.utils.timezone import now

from exchange.base.models import AVAILABLE_CURRENCIES, RIAL, XCHANGE_CURRENCIES, get_currency_codename
from exchange.shetab.models import ShetabDeposit
from exchange.wallet.models import ConfirmedWalletDeposit, WithdrawRequest


def access_status_reports(user):
    if not user.is_staff:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=['support', 'developer']).exists()


@user_passes_test(access_status_reports)
def overview(request):
    reports = {}
    date_filter = Q(created_at__gt=now() - datetime.timedelta(hours=24))
    if settings.DEBUG:
        date_filter = Q()
    for currency in AVAILABLE_CURRENCIES + XCHANGE_CURRENCIES:
        if currency == RIAL:
            deposits = ShetabDeposit.objects.filter(
                date_filter,
                transaction__isnull=False,
            ).select_related('user').order_by('-amount')[:20]
        else:
            # TODO: Are these select_related necessary?
            deposits = ConfirmedWalletDeposit.objects.filter(
                date_filter,
                address__currency=currency,
                confirmed=True,
                validated=True,
            ).select_related('address', '_wallet', 'address__wallet', 'address__wallet__user').order_by('-amount')[:20]
        withdraws = WithdrawRequest.objects.filter(
            date_filter,
            wallet__currency=currency,
            status__gte=WithdrawRequest.STATUS.verified,
        ).select_related('wallet', 'wallet__user').order_by('-amount')[:20]
        reports[get_currency_codename(currency).upper()] = {
            'deposits': deposits,
            'withdraws': withdraws,
            'users': [],
        }
    return render(request, 'status/overview.html', {
        'reports': reports,
    })
