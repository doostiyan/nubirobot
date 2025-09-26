from datetime import date

from django.core.management.base import BaseCommand, CommandError

from exchange.asset_backed_credit.models import AssetToDebtMarginCall


class Command(BaseCommand):
    help = "Update last margin call actions"

    def handle(self, *args, **options):
        total = self.update_last_action()
        self.stdout.write(self.style.SUCCESS(f'Successfully updated {total} margin calls.'))

    @staticmethod
    def update_last_action():
        return AssetToDebtMarginCall.objects.filter(
            orders__isnull=False, last_action=10, created_at__date__lte=date(year=2024, month=6, day=23)
        ).update(last_action=30)
