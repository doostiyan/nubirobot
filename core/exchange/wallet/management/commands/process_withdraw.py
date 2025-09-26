import time

from django.core.management.base import BaseCommand

from exchange.base.parsers import parse_currency
from exchange.wallet.withdraw import process_withdraws


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('currency', nargs='*', default='')
        parser.add_argument(
            '--exclude',
            nargs='*',
            help='Exclude currencies',
        )
        parser.add_argument(
            '--networks',
            nargs='*',
            help='Networks',
        )
        parser.add_argument(
            '--exclude_networks',
            nargs='*',
            help='Exclude Networks',
        )
        parser.add_argument(
            '--time-interval',
            type=int,
            default=5,
            help='Time interval between each run',
        )
        parser.add_argument(
            '--h_index',
            type=int,
            default=0,
            help='Hotwallet index',
        )
        parser.add_argument(
            '--n_hotwallets',
            type=int,
            default=1,
            help='Hotwallet number of workers',
        )

    def handle(self, *args, **kwargs):
        currencies = [parse_currency(c) for c in kwargs.get('currency', [])]
        exclude_currencies = [parse_currency(c) for c in kwargs.get('exclude') or []]
        networks = [n for n in kwargs.get('networks') or []]
        exclude_networks = [n for n in kwargs.get('exclude_networks') or []]
        hotwallet_index = kwargs.get('h_index', 0)
        hotwallet_numbers = kwargs.get('n_hotwallets', 1)
        try:
            while True:
                process_withdraws(
                    currencies=currencies or None,
                    exclude_currencies=exclude_currencies or None,
                    networks=networks or None,
                    exclude_networks=exclude_networks or None,
                    hotwallet_index=hotwallet_index,
                    hotwallet_numbers=hotwallet_numbers,
                )
                print('')
                time.sleep(kwargs.get('time_interval'))
        except KeyboardInterrupt:
            print('bye!')
