from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.asset_backed_credit.models import Service


class Command(BaseCommand):
    help = "Set is_available field on services"

    @transaction.atomic
    def handle(self, *args, **options):
        total = Service.objects.filter(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan).update(
            is_available=True
        )

        self.stdout.write(
            self.style.SUCCESS(f'Command Done, {total} services updated.'),
        )
