""" Sequential Balance Updater """
import datetime
import random
import time

from django.db.models import F, Q
from django.utils.timezone import now

from exchange.base.models import Currencies, CURRENCY_CODENAMES
from exchange.wallet.deposit import update_address_balances_for_currency
from exchange.wallet.models import WalletDepositAddress


def update_wallet_balances(selection=None, currencies=None, size=None):
    if currencies is None:
        currencies = [
            Currencies.btc, Currencies.eth, Currencies.ltc, Currencies.usdt,
            Currencies.bch, Currencies.doge, Currencies.trx, Currencies.etc,
        ]
    pr = {
        Currencies.btc: 75, Currencies.eth: 75, Currencies.ltc: 100,
        Currencies.usdt: 75, Currencies.bch: 50,
    }
    min_balance = {
        Currencies.btc: 0.01, Currencies.eth: 0.1, Currencies.ltc: 1, Currencies.bch: 1,
        Currencies.usdt: 100, Currencies.trx: 20000, Currencies.doge: 20000, Currencies.etc: 1,
    }
    rnd = 0
    while True:
        if rnd == 0:
            rnd_start = time.time()
            fails = {}
            success = {}
        nw = now()
        rnd += 1
        addresses = {}
        batch_size = 1
        fetch_size = size or 50
        round_currencies = []

        # wallet selection method
        if selection:
            selection_method = selection
        else:
            selection_method = 'oldest'

        # Select wallets to check
        if selection_method == 'oldest':
            for currency in currencies:
                if random.randint(0, 100) < pr.get(currency, 100):
                    round_currencies.append(currency)
            for currency in round_currencies:
                to_check = WalletDepositAddress.objects.filter(currency=currency)
                addresses[currency] = list(to_check.order_by('last_update_check')[:fetch_size])
        elif selection_method == 'largest':
            round_currencies = currencies
            for currency in round_currencies:
                addresses[currency] = list(WalletDepositAddress.objects.annotate(
                    _current_balance=F('total_received') - F('total_sent'),
                ).filter(
                    currency=currency,
                    last_update_check__lt=nw - datetime.timedelta(hours=1),
                ).order_by('-_current_balance')[:fetch_size])
        elif selection_method == 'balances':
            round_currencies = currencies
            for currency in round_currencies:
                delta = min_balance.get(currency, 1)
                addresses[currency] = list(WalletDepositAddress.objects.filter(
                    Q(total_received__gt=delta * 10, last_update_check__lt=nw - datetime.timedelta(hours=1)) |
                    Q(total_received__gt=delta, last_update_check__lt=nw - datetime.timedelta(hours=6)) |
                    Q(total_received__gt=delta * 0.1, last_update_check__lt=nw - datetime.timedelta(hours=24)),
                    currency=currency,
                ).order_by('-total_received')[:fetch_size])

        # Check balances
        for _ in range(fetch_size):
            for currency in round_currencies:
                try:
                    address = addresses[currency].pop(0)
                except IndexError:
                    continue
                if currency == Currencies.usdt and False:
                    address_list = {'TRX': [address]}
                else:
                    address_list = [address]
                try:
                    updates = update_address_balances_for_currency(address_list, quiet=True)
                except:
                    time.sleep(2)
                    updates = 0
                success[currency] = success.get(currency, 0) + updates
                if updates < batch_size:
                    fails[currency] = fails.get(currency, 0) + batch_size - updates
                    print('!' + CURRENCY_CODENAMES.get(currency), end=' ', flush=True)
            time.sleep(0.1)

        if rnd == 1:
            print('[{}s]'.format(round(time.time() - rnd_start)), end=' ')
            for currency in currencies:
                print('{}={}/{}'.format(
                    CURRENCY_CODENAMES.get(currency),
                    success.get(currency, 0),
                    fails.get(currency, 0),
                ), end=' ')
            print('', flush=True)
            rnd = 0
        if sum(fails.values()) > 10:
            print('Too many failures, waiting for 5 seconds...')
            time.sleep(5)
        if sum(success.values()) < 25:
            print('Too few successes, waiting for 5 seconds...')
            time.sleep(5)
        time.sleep(1)


def run_sequential_balance_updater(**kwargs):
    print('Updating all wallet balances...')
    try:
        update_wallet_balances(**kwargs)
    except KeyboardInterrupt:
        pass
