from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand

from exchange.base.models import Currencies

if settings.BLOCKCHAIN_SERVER:
    from exchange.wallet.crons import confirm_tagged_deposits


class Command(BaseCommand):
    """
        This command with confirm tagged deposits defaults for hmstr on TON in a given period of time.

        Run with:
            python manage.py confirmdeposits --start-date=<timestamp> --end-date=<timestamp>
        or simply:
            python manage.py confirmdeposits
        and let the command get needed inputs by shell
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--network',
            type=str,
            nargs='?',
            help='the network ',
            default='TON'
        )
        parser.add_argument(
            '--currency',
            type=int,
            nargs='?',
            help='the currency',
            default=Currencies.hmstr,
        )
        parser.add_argument(
            '--start-date',
            type=int,
            nargs='?',
            help='the start date timestamp'
        )
        parser.add_argument(
            '--end-date',
            type=int,
            nargs='?',
            help='the end date timestamp'
        )

    def handle(self, *args, **kwargs):
        network = kwargs.get('network').upper()
        currency = kwargs.get('currency')

        start_date = kwargs.get('start-date')
        end_date = kwargs.get('end-date')

        if not start_date:
            start_date = int(input('Enter start date timestamp: '))

        if not end_date:
            end_date = int(input('Enter end date timestamp: '))

        # set cache to use get_token_txs_by_time_with_retry in BlockchainExplorer for given period of time
        cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}token_txs_retry', True)
        cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}token_txs_start_date', start_date)
        cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}token_txs_end_date', end_date)

        confirm_tagged_deposits(currency=currency, network=network)
