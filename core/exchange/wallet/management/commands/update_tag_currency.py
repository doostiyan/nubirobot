from django.core.management.base import BaseCommand
from django.db import transaction
from tqdm import tqdm

from exchange.wallet.models import WalletDepositTag


class Command(BaseCommand):
    help = 'Update currency field for existing WalletDepositTag records'

    def handle(self, *args, **kwargs):
        tags = WalletDepositTag.objects.filter(currency=0).select_related('wallet').all()

        for tag in tqdm(tags, desc="Updating currency in tags"):
            if tag.currency != tag.wallet.currency:
                tag.currency = tag.wallet.currency
                tag.save(update_fields=['currency'])

        self.stdout.write(self.style.SUCCESS('Successfully updated currency for all applicable tags.'))
