import time

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from exchange.base.parsers import parse_currency
from exchange.wallet.withdraw_diff import to_done_tagged_withdraws


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('currencies', nargs='*', default='')

    def handle(self, *args, **kwargs):
        currencies = [parse_currency(c) for c in kwargs.get('currencies', [])]
        while True:
            try:
                start_time = now()
                to_done_tagged_withdraws(currencies)
                end_time = now()
                print(f'[WithdarwDiff] Spent time:' f'{(end_time - start_time).seconds} seconds')
                time.sleep(5)
            except KeyboardInterrupt:
                print('bye!')
                break
            except Exception as e:
                print(f'[WithdarwDiff] custom service API Error: {e}')
                time.sleep(5)
