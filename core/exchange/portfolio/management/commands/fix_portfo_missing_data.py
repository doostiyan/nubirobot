import datetime
from decimal import Decimal

from django.core.management import BaseCommand
from django.db import transaction

from exchange.portfolio.models import UserTotalDailyProfit


class Command(BaseCommand):
    help = """24th Esfand, Cron was not successfully run. And 25th, initial balances were not set.
    After 24th being filled with data, 25th data has to be fixed
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Print output of run data',
        )
        parser.add_argument('--day', type=str, help='The Day that records will be updated for')
        parser.add_argument(
            '--batch-size',
            '-b',
            type=int,
            default=1000,
            help='Specify the batch size for processing (default: 1000)',
        )

    def handle(self, *args, **kwargs):
        verbose = kwargs.get('verbose')
        batch_size = kwargs['batch_size']
        day = datetime.datetime.strptime(kwargs['day'], '%Y-%m-%d').date()
        yesterday = day - datetime.timedelta(days=1)

        initial_balances_queryset = UserTotalDailyProfit.objects.filter(report_date=yesterday).values(
            'user_id', 'total_balance'
        )
        if verbose:
            self.stdout.write(self.style.SUCCESS(f'{initial_balances_queryset.count()} records found for {yesterday.isoformat()}'))

        initial_balances = {r['user_id']: max(r['total_balance'], Decimal(0)) for r in initial_balances_queryset}
        profits = UserTotalDailyProfit.objects.filter(report_date=day).order_by('id').iterator(chunk_size=batch_size)
        if verbose:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Found {UserTotalDailyProfit.objects.filter(report_date=day).count()} records for {day.isoformat()} to update'
                )
            )
        batch = []
        total_updated = 0
        for profit in profits:
            initial_balance = initial_balances.get(profit.user_id, Decimal(0))
            cost = initial_balance + profit.total_deposit
            revenue = profit.total_balance + profit.total_withdraw

            profit.profit = revenue - cost if cost else Decimal(0)
            profit.profit_percentage = min(profit.profit / cost * 100, Decimal(10_000)) if cost else Decimal(0)

            batch.append(profit)
            if len(batch) >= batch_size:
                with transaction.atomic():
                    update_count = UserTotalDailyProfit.objects.bulk_update(batch, ['profit', 'profit_percentage'])
                total_updated += update_count
                batch = []
                if verbose:
                    self.stdout.write(
                        self.style.SUCCESS(f'Just updated {update_count} records. Total updated: {total_updated}')
                    )
        if batch:
            with transaction.atomic():
                update_count = UserTotalDailyProfit.objects.bulk_update(batch, ['profit', 'profit_percentage'])
            total_updated += update_count
            if verbose:
                self.stdout.write(self.style.SUCCESS(f'Final batch updated {update_count} Records.'))
        self.stdout.write(self.style.SUCCESS(f'Total updated: {total_updated}'))
