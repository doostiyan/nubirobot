from django.core.management.base import BaseCommand
from tqdm import tqdm

from exchange.accounts.models import BankAccount


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            '-b',
            type=int,
            default=100,
            help='Specify the batch size for processing (default: 100)',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']

        blu_accounts = BankAccount.objects.filter(
            bank_id=BankAccount.BANK_ID.saman,
            account_number__startswith='6118',
            account_number__contains='-',
        )

        accounts_to_update = []
        i = 0

        for account in tqdm(blu_accounts):
            if not account.is_blu:  # Just to make sure
                continue

            if '-' not in account.account_number:
                continue

            i += 1
            account.account_number = account.shaba_number[-18:]
            accounts_to_update.append(account)

            if i % batch_size == 0 and accounts_to_update:
                BankAccount.objects.bulk_update(accounts_to_update, fields=['account_number'])
                accounts_to_update = []

        if accounts_to_update:
            BankAccount.objects.bulk_update(accounts_to_update, fields=['account_number'])

        self.stdout.write(self.style.SUCCESS(f'Updated {i} accounts'))
