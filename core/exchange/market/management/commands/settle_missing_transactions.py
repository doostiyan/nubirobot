import datetime

from django.core.management.base import BaseCommand

from exchange.base.calendar import ir_now
from exchange.market.functions import create_missing_transaction


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--from_n_days_ago', type=int, help='For filter until the desired date')
        parser.add_argument('--to_n_days_ago', type=int, help='For filter from the desired date')
        parser.add_argument('--dry_run', action='store_true', help='To run without effect')

    def handle(self, from_n_days_ago, to_n_days_ago, dry_run, **kwargs):

        from_datetime = ir_now() - datetime.timedelta(days=int(from_n_days_ago))
        to_datetime = ir_now() - datetime.timedelta(days=int(to_n_days_ago))

        create_missing_transaction(from_datetime, to_datetime, disable_process_bar=False, dry_run=dry_run)

