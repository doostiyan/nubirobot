from django.core.management.base import BaseCommand
from django.db.models import Count, Max, OuterRef, Subquery

from exchange.direct_debit.models import DailyDirectDeposit


class Command(BaseCommand):
    """
    Examples:
        python manage.py remove_duplicated_daily_deposit
    """

    help = 'Remove duplicated daily deposits'

    def handle(self, **options):
        newest_records = (
            DailyDirectDeposit.objects.filter(trace_id=OuterRef('trace_id')).order_by('-id').values('id')[:1]
        )

        deleted_count, _ = DailyDirectDeposit.objects.exclude(id__in=Subquery(newest_records)).delete()

        self.stdout.write(self.style.SUCCESS('Done'))
