from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.asset_backed_credit.models import Card, CardSetting


class Command(BaseCommand):
    help = "Create default limitations for debit card and adds level one to all cards with no levels"

    @transaction.atomic
    def handle(self, *args, **options):
        level_one, _ = CardSetting.objects.get_or_create(
            level=CardSetting.DEFAULT_CARD_LEVEL,
            defaults={
                'label': 'سطح یک',
                'per_transaction_amount_limit': 100_000_000,
                'daily_transaction_amount_limit': 100_000_000,
                'monthly_transaction_amount_limit': 100_000_000,
                'cashback_percentage': 0.0,
            },
        )
        level_two, _ = CardSetting.objects.get_or_create(
            level=2,
            defaults={
                'label': 'سطح دو',
                'per_transaction_amount_limit': 1_000_000_000,
                'daily_transaction_amount_limit': 1_000_000_000,
                'monthly_transaction_amount_limit': 5_000_000_000,
                'cashback_percentage': 0.0,
            },
        )

        self.stdout.write(self.style.SUCCESS(f'Added card level one and level two'))

        Card.objects.filter(setting__isnull=True).update(setting=level_one)
        self.stdout.write(self.style.SUCCESS(f'Added level one to all existing cards with null levels '))
