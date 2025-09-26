import time

from django.core.management.base import BaseCommand

from exchange.base.parsers import parse_currency
from exchange.wallet.balances import run_sequential_balance_updater
from exchange.wallet.deposit import update_address_balances


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('currency', nargs='*', default='')
        parser.add_argument('--all', action='store_true', help='Run new balance updater daemon for all wallets')
        parser.add_argument('--top', action='store_true', help='Run new balance updater daemon for top balances')

    def handle(self, *args, all=False, top=False, **kwargs):
        if all:
            run_sequential_balance_updater()
            return
        if top:
            run_sequential_balance_updater(selection='balances', currencies=[10, 11, 12, 13, 15, 18, 20, 25])
            return
        currencies = [parse_currency(c) for c in kwargs.get('currency', [])]
        try:
            while True:
                print('===> Checking Wallet Balances ({})'.format(str(currencies)))
                update_address_balances(currencies=currencies or None)
                print('.')
                time.sleep(60)
        except KeyboardInterrupt:
            print('bye!')
