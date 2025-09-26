from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils.timezone import make_aware

from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from exchange.report.crons import SaveDailyDirectDeposits


class Command(BaseCommand):
    """
    Examples:
        python manage.py faraboom_sync
    """

    help = 'Sync Faraboom daily deposits'

    def add_arguments(self, parser):
        parser.add_argument('--period', help='Period of inquiry range in hours', type=int, default=12)

    def handle(self, **options):
        period = timedelta(hours=options['period'])
        from_date = Settings.get_datetime(
            SaveDailyDirectDeposits.SENTINEL_NAME, make_aware(datetime(2024, 3, 1, 0, 0, 0))
        )

        while from_date < ir_now():
            to_date = from_date + period - SaveDailyDirectDeposits.guard_duration
            SaveDailyDirectDeposits().update_items(from_date=from_date, to_date=to_date)
            self.stdout.write(self.style.SUCCESS(f'Synced from {from_date} to {to_date}'))
            from_date = to_date

        self.stdout.write(self.style.SUCCESS('Done'))
