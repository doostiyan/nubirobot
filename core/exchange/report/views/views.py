import string
from decimal import Decimal

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.core.cache import cache
from django.db.models import F, Q, Sum
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from exchange.base.logging import report_exception
from exchange.base.models import (
    ACTIVE_CRYPTO_CURRENCIES,
    ALL_CRYPTO_CURRENCIES,
    CURRENCY_CODENAMES,
    Currencies,
    Settings,
    get_currency_codename,
)
from exchange.base.parsers import parse_int
from exchange.blockchain.metrics import metrics_conf as blockchain_metrics_conf
from exchange.blockchain.metrics import metrics_get as get_blockchain_metrics
from exchange.metrics.helpers import monitoring_api
from exchange.report.forms import ControlPanelForm
from exchange.report.metrics import (
    COUNTER_METRICS_WITH_LABELS,
    COUNTER_METRICS_WITH_NO_LABELS,
    TIME_METRICS_WITH_LABELS,
    TIME_METRICS_WITH_NO_LABELS,
)
from exchange.report.periodic_metrics_calculator import PeriodicMetricsCalculator
from exchange.wallet.deposit import update_address_balances_for_currency
from exchange.wallet.models import AvailableHotWalletAddress, SystemColdAddress, WalletDepositAddress


def escape_metric_value(value: str) -> str:
    acceptable_metric_value_characters = string.ascii_letters + string.digits + '_'
    return ''.join([c for c in value if c in acceptable_metric_value_characters])


def admin_access(user):
    return user.is_superuser


def staff_access(user):
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=['support', 'developer', 'accountant']).exists()


@staff_member_required
@user_passes_test(staff_access)
def wallets_overview(request):
    currencies = ALL_CRYPTO_CURRENCIES

    # hot wallets
    hot_wallets = AvailableHotWalletAddress.objects.annotate(
        _current_balance=F('total_received') - F('total_sent'),
    ).order_by('currency', '-_current_balance')
    hot_balances = sum_wallet_balance(hot_wallets)
    for w in hot_wallets:
        # Estimate dollar value
        if w.currency == Currencies.usdt:
            usdt_price = 1
        else:
            usdt_price = (
                cache.get(
                    f'orderbook_{CURRENCY_CODENAMES[w.currency]}USDT_best_active_sell',
                )
                or Decimal('0')
            )
        w.balance_value = w.current_balance * usdt_price

    # System cold addresses
    system_cold_addresses = SystemColdAddress.objects.filter(
        is_disabled=False,
    ).annotate(
        _current_balance=F('total_received') - F('total_sent'),
    ).order_by('currency', '-_current_balance')
    system_cold_balances = sum_wallet_balance(system_cold_addresses)

    # cold wallets
    cold_wallets = [
        WalletDepositAddress.objects.annotate(
            _current_balance=F('total_received') - F('total_sent'),
        ).filter(
            _current_balance__gt=0,
            currency=c,
        ).order_by('-_current_balance').select_related(
            'wallet', 'wallet__user',
        ) for c in currencies
    ]
    cold_balances = [w.aggregate(s=Sum('_current_balance'))['s'] or Decimal('0') for w in cold_wallets]
    cold_wallets = [wallets[:10] for wallets in cold_wallets]

    return render(
        request,
        'report/wallets.html',
        {
            'currencies': [get_currency_codename(c).upper() for c in currencies],
            'hot_wallets': hot_wallets,
            'hot_balances': hot_balances,
            'system_cold_addresses': system_cold_addresses,
            'system_cold_balances': system_cold_balances,
            'cold_wallets': cold_wallets,
            'cold_balances': cold_balances,
            'sum_balances': [sum(x) for x in zip(hot_balances, cold_balances, system_cold_balances)],
        },
    )


def sum_wallet_balance(wallets):
    """ Return value: [sum(btc), sum(eth), ...]
    """
    balances = []
    for currency in ALL_CRYPTO_CURRENCIES:
        balance = 0
        for wallet in wallets:
            if hasattr(wallet, 'wallet'):
                if wallet.wallet.currency == currency:
                    balance += wallet.current_balance
                continue
            if wallet.currency == currency:
                balance += wallet.current_balance
        balances.append(balance)
    return balances


@csrf_exempt
@staff_member_required
@user_passes_test(staff_access)
def wallets_update_balance(request):
    wallets = []
    action = request.POST.get('action')
    wallet_pk = parse_int(request.POST.get('wallet'))
    if action == 'update-cold':
        wallets = WalletDepositAddress.objects.filter(
            Q(pk=wallet_pk) if wallet_pk else Q(),
        ).select_related('wallet')
    elif action == 'update-cold-system':
        wallets = SystemColdAddress.objects.filter(Q(pk=wallet_pk) if wallet_pk else Q())
    elif action == 'update-hot':
        wallets = AvailableHotWalletAddress.objects.filter(Q(pk=wallet_pk) if wallet_pk else Q())
    if wallets:
        for c in ACTIVE_CRYPTO_CURRENCIES:
            currency_wallets = [w for w in wallets if w.currency == c]
            if currency_wallets:
                update_address_balances_for_currency(currency_wallets, sleep=3)
    return redirect('/bitex/wallets')


@staff_member_required
@user_passes_test(admin_access)
def control_panel(request):
    generic_fields = [
        'module_matching_engine',
        'module_autotrader_engine',
        'module_withdraw_processing',
        'module_deposit_processing',
    ]
    if request.method == 'POST':
        form = ControlPanelForm(request.POST)
        if form.is_valid():
            # Generic Fields
            for k, v in form.cleaned_data.items():
                if k not in generic_fields:
                    continue
                Settings.set(k, v)
    else:
        # Current value for generic fields
        initial = {k: Settings.get(k) for k in generic_fields}
        # Initialize the form
        form = ControlPanelForm(initial=initial)
    return render(request, 'report/control_panel.html', {
        'form': form,
    })


@monitoring_api
def nobitex_metrics(request):
    selected_modules_str = request.GET.get('modules')
    selected_modules = selected_modules_str.split(',') if selected_modules_str else ['basic']

    if 'basic' in selected_modules:
        selected_modules += ['importantPrices', 'celery']

    periodic_metric_calculator = PeriodicMetricsCalculator(target='redis', selected_modules=selected_modules)

    # Periodic Metrics
    periodic_metric_calculator.set_metrics()
    metrics = periodic_metric_calculator.get_metrics()

    # Timing Metrics
    if 'timings' in selected_modules:
        # Timing Metrics with no labels
        for metric in TIME_METRICS_WITH_NO_LABELS:
            metrics[f'nobitex_{metric}'] = cache.get(f'time_{metric}_avg') or 0

        # Timing Metrics with labels
        time_cache_keys = cache.keys('time_*')
        for metric, labels in TIME_METRICS_WITH_LABELS.items():
            metric_cache_keys = filter(lambda k: k.startswith(f'time_{metric}__'), time_cache_keys)
            for metric_key in metric_cache_keys:
                raw_key = metric_key[: -len('_avg')]
                parts = raw_key.split('__', 1)
                if len(parts) < 2:
                    continue
                labels_values = parts[1].split('_')
                key_labels = []
                for label_name, label_value in zip(labels, labels_values):
                    key_labels.append(f'{label_name}="{escape_metric_value(label_value)}"')
                key_str = f'nobitex_{metric}'
                if key_labels:
                    key_str += '{' + ','.join(key_labels) + '}'
                metrics[key_str] = cache.get(metric_key) or 0

    # Counter Metrics
    if 'counters' in selected_modules:
        for metric_key in cache.keys('metric_*'):
            parts = metric_key.split('__', 1)
            if len(parts) < 2:
                metric_name = parts[0][7:]
                if metric_name in COUNTER_METRICS_WITH_NO_LABELS:
                    metrics[f'nobitex_{metric_name}'] = cache.get(metric_key) or 0
                continue
            metric_name = parts[0][7:]
            if metric_name not in COUNTER_METRICS_WITH_LABELS:
                continue
            labels = COUNTER_METRICS_WITH_LABELS[metric_name]
            labels_values = parts[1].split('_')
            key_labels = []
            for label_name, label_value in zip(labels, labels_values):
                label_value_safe = escape_metric_value(label_value)
                key_labels.append(f'{label_name}="{label_value_safe}"')
            key_str = f'nobitex_{metric_name}'
            if key_labels:
                key_str += '{' + ','.join(key_labels) + '}'
            metrics[key_str] = cache.get(metric_key) or 0

    if 'blockchain' in selected_modules:  # TODO: decide about blockchain metrics
        try:
            for blockchain_metric in list(blockchain_metrics_conf.keys()):
                for metric_key, metric_value in get_blockchain_metrics(blockchain_metric).items():
                    metrics[metric_key] = metric_value
        except Exception:  # noqa: BLE001
            report_exception()

    # Change namespace for testnet
    if settings.IS_TESTNET:
        testnet_metrics = {}
        for key, value in metrics.items():
            testnet_key = 'testnet_' + key[8:] if key.startswith('nobitex_') else 'testnet_' + key
            testnet_metrics[testnet_key] = value
        metrics = testnet_metrics

    metrics_safe = {}
    for k, v in metrics.items():
        key = k.replace('-', '_').replace('\n', '_')
        metrics_safe[key] = v
    return render(request, 'metrics.html', {'metrics': metrics_safe}, content_type='text/plain')
