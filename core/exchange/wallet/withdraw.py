import datetime
from collections import defaultdict

from django.conf import settings
from django.db.models import F, Q

from exchange.accounts.models import BankAccount
from exchange.base.calendar import ir_now
from exchange.base.helpers import context_flag
from exchange.base.models import (
    ALL_CURRENCIES,
    FIAT_CURRENCIES,
    NOT_COIN,
    RIAL,
    Currencies,
    Settings,
    get_currency_codename,
)
from exchange.wallet.models import WithdrawRequest
from exchange.wallet.withdraw_process import ProcessingWithdrawMethod

WithdrawProcessor = {currency: ProcessingWithdrawMethod(currency=currency) for currency in ALL_CURRENCIES}

# Monero Change MIN/MAX timeout for batch requests
if Currencies.xmr in WithdrawProcessor:
    WithdrawProcessor[Currencies.xmr].min_batch_timeout = 600
    WithdrawProcessor[Currencies.xmr].max_batch_timeout = 1200
    WithdrawProcessor[Currencies.xmr].max_batch_size = 9

if Currencies.sol in WithdrawProcessor:
    WithdrawProcessor[Currencies.sol].max_batch_size = 19

if Currencies.ton in WithdrawProcessor:
    WithdrawProcessor[Currencies.ton].max_batch_size = 60

if Currencies.dogs in WithdrawProcessor:
    WithdrawProcessor[Currencies.dogs].max_batch_size = 30

if Currencies.hmstr in WithdrawProcessor:
    WithdrawProcessor[Currencies.dogs].max_batch_size = 30

if NOT_COIN in WithdrawProcessor:
    WithdrawProcessor[NOT_COIN].max_batch_size = 30

if Currencies.x in WithdrawProcessor:
    WithdrawProcessor[Currencies.x].max_batch_size = 30

if Currencies.major in WithdrawProcessor:
    WithdrawProcessor[Currencies.major].max_batch_size = 30


def is_auto_withdraw_enabled():
    return Settings.get_flag("withdraw_enabled")


@context_flag(NOTIFY_NON_ATOMIC_TX_COMMIT=False)
def process_withdraws(
    withdraws=None,
    manual=False,
    currencies=None,
    exclude_currencies=None,
    networks=None,
    exclude_networks=None,
    hotwallet_index: int = 0,
    hotwallet_numbers: int = 1,
):
    """Process all withdraw automatically.
    Only process once. If fails does not retry automatically.
    """
    if currencies is None:
        currencies = ALL_CURRENCIES
    if exclude_currencies is not None:
        currencies = [c for c in currencies if c not in exclude_currencies]
    crypto_currencies = [c for c in currencies if c not in FIAT_CURRENCIES]
    print('=' * 30)
    if not is_auto_withdraw_enabled() and not manual:
        print('[Notice] Withdraw Processing Disabled')
        return
    if Settings.is_disabled('module_withdraw_processing') and not manual:
        print('[Notice] Withdraw Processing Disabled')
        return
    all_withdraw_requests = withdraws
    if not all_withdraw_requests:
        # Filter currency based on currencies parameter
        q_coin_requests = Q(wallet__currency__in=crypto_currencies)
        q_currency_requests = q_coin_requests
        if RIAL in currencies:
            q_rial_requests = Q(target_account__bank_id=BankAccount.BANK_ID.ayandeh)
            q_rial_internal = Q(tp=WithdrawRequest.TYPE.internal, wallet__currency=RIAL)
            q_currency_requests = q_currency_requests | q_rial_requests | q_rial_internal
        # Only get new withdraws
        q_new_requests = Q(created_at__gt=ir_now() - datetime.timedelta(days=3))
        # Get withdraws for this round.
        q_networks = Q()
        if networks is not None:
            q_networks = q_networks & Q(network__in=networks)
        if exclude_networks is not None:
            q_networks = q_networks & ~Q(network__in=exclude_networks)
        all_withdraw_requests = WithdrawRequest.objects.filter(
            q_currency_requests, q_new_requests, q_networks,
            status__in=WithdrawRequest.STATUSES_PENDING,
        )
        # Split withdraws to workers
        if hotwallet_numbers > 1:
            all_withdraw_requests = all_withdraw_requests.annotate(h_index=F('id') % hotwallet_numbers).filter(
                h_index=hotwallet_index
            )
        all_withdraw_requests = all_withdraw_requests.select_related(
            'wallet', 'wallet__user', 'transaction').prefetch_related('auto_withdraw').order_by(
            'status', 'wallet__currency', 'created_at'
        )

    withdraw_requests_status = defaultdict(lambda: defaultdict(list))

    for withdraw_req in all_withdraw_requests:
        withdraw_requests_status[withdraw_req.status][withdraw_req.currency].append(withdraw_req)

    withdraw_requests_status = sorted(withdraw_requests_status.items(),
                                      key=lambda i: WithdrawRequest.STATUSES_ORDER.index(i[0]))

    for status, w_requests_status in withdraw_requests_status:
        if len(w_requests_status):
            status_msg = f'Processing Status: {WithdrawRequest.status_display(status)}'
            status_msg = status_msg.ljust(25) + f'[{len(w_requests_status)}]'
            print(status_msg)

        for currency, w_requests in w_requests_status.items():
            print(f'  => {get_currency_codename(currency)}')
            w_requests = w_requests[:500]
            if currency in WithdrawProcessor:
                WithdrawProcessor[currency].process_withdraws(w_requests, status, hotwallet_index=hotwallet_index)
    print('*' * 30)
