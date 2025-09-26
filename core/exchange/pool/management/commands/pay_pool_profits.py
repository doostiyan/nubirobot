from datetime import date
from time import sleep

from django.core.management.base import BaseCommand, CommandError

from exchange.base.models import Currencies
from exchange.pool.errors import ConversionOrderException, PartialConversionOrderException
from exchange.pool.functions import distribute_profits_for_target_pools, populate_daily_profit_for_target_pools
from exchange.pool.models import LiquidityPool, UserDelegationProfit


class Command(BaseCommand):
    """Examples
    python manage.py pay_pool_profits -f 2022-04-27 -t 2022-05-26
    python manage.py pay_pool_profits -c btc -f 2022-04-27 -t 2022-05-26
    python manage.py pay_pool_profits -c btc -f 2022-04-27 -t 2022-05-11 -p 2022-05-26
    """

    help = 'Pay pool profits for a period.'

    def add_arguments(self, parser):
        parser.add_argument('-c', '--currency', type=str, help='Pool currency [e.g. btc]', default=None)
        parser.add_argument(
            '-f',
            '--from-date',
            type=str,
            help='Start of period [use YYYY-MM-DD format]',
        )
        parser.add_argument(
            '-t',
            '--to-date',
            type=str,
            help='End of period [use YYYY-MM-DD format]',
        )
        parser.add_argument(
            '-p',
            '--positions-to-date',
            type=str,
            help='Last close date to take for positions [use YYYY-MM-DD format]',
            default=None,
        )
        parser.add_argument(
            '-r',
            '--reset-apr',
            action='store_true',
            help='Reset pool apr',
        )

    def handle(self, currency: str, from_date: str, to_date: str, positions_to_date: str, reset_apr: bool, **options):
        pools = LiquidityPool.objects.all()
        if currency:
            try:
                currency_code = getattr(Currencies, currency.lower())
            except AttributeError:
                raise CommandError(f"Invalid currency '{currency}'.")
            pools = LiquidityPool.objects.filter(currency=currency_code)
        # Delete invalid objects
        udps = UserDelegationProfit.objects.filter(amount__isnull=True, user_delegation__pool__in=pools)
        udps.delete()

        from_date = date.fromisoformat(from_date)
        to_date = date.fromisoformat(to_date)
        positions_to_date = date.fromisoformat(positions_to_date) if positions_to_date else to_date
        populate_daily_profit_for_target_pools(from_date, positions_to_date, pools)

        if reset_apr:
            print('Resetting APR...')
            pools.update(apr=None)

        for i in range(10):
            try:
                print(f'Paying user profits, try #{i}...')
                distribute_profits_for_target_pools(from_date, to_date, pools, positions_to_date)
                print('DONE!')
                break
            except (PartialConversionOrderException, ConversionOrderException):
                sleep(0.3)
