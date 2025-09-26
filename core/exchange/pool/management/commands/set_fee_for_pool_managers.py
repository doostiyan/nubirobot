from decimal import Decimal

from django.core.management.base import BaseCommand

from exchange.accounts.models import User
from exchange.pool.models import LiquidityPool


class Command(BaseCommand):
    help = 'Sets a global fee for all pool managers'

    def add_arguments(self, parser):
        parser.add_argument('--exclude', type=str, required=False, default='', help='Currencies to exclude')
        parser.add_argument('--rial-fee', type=Decimal)
        parser.add_argument('--usdt-fee', type=Decimal)

    def handle(self, **options):
        excluded_currencies = list(map(int, options['exclude'].split(',')))
        pool_managers = LiquidityPool.objects.exclude(currency__in=excluded_currencies).values_list(
            'manager_id', flat=True
        )

        rows = User.objects.filter(id__in=pool_managers).update(
            base_fee=options['rial_fee'],
            base_maker_fee=options['rial_fee'],
            base_fee_usdt=options['usdt_fee'],
            base_maker_fee_usdt=options['usdt_fee'],
        )

        self.stdout.write(f'{rows} users updated')
