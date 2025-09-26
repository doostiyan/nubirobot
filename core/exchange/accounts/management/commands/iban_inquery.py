from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from time import sleep

import requests
from django.core.management.base import BaseCommand
from tqdm import tqdm

from exchange.accounts.models import BankAccount
from exchange.base.calendar import ir_now
from exchange.base.logging import report_exception
from exchange.integrations.jibit import JibitVerificationClient
from exchange.integrations.types import IbanInquiry


class Command(BaseCommand):
    test_account_ids = [8240356, 1954985, 31541, 42613, 34934]

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            '-b',
            type=int,
            default=100,
            help='Specify the batch size for processing (default: 100)',
        )
        parser.add_argument(
            '--test',
            '-t',
            action='store_true',
            help='Run command on test accounts only',
        )
        parser.add_argument(
            '--threads',
            type=int,
            default=4,
            help='Number of threads for requests',
        )
        parser.add_argument(
            '--from-days-ago',
            type=int,
            default=1,
            help='Get objects from n days ago',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        from_days_ago = options['from_days_ago']

        threads = options['threads']
        self.stdout.write(self.style.SUCCESS('Starting...'))
        failed_accounts = []
        bank_accounts = BankAccount.objects.filter(
            is_deleted=False,
            account_number__in=['0', ''],
            confirmed=True,
            created_at__gte=ir_now() - timedelta(days=from_days_ago),
        ).order_by('id')

        test_mode = options.get('test')
        if test_mode:
            bank_accounts = bank_accounts.filter(user_id__in=self.test_account_ids)
            self.stdout.write(self.style.SUCCESS('Running in test mode'))

        if not bank_accounts.exists():
            self.stdout.write(self.style.SUCCESS('No records to update'))
            return

        number_of_updated_objects = 0
        with tqdm(total=bank_accounts.count()) as progress_bar:
            last_visited_id = -1
            while chunk_of_bank_accounts := bank_accounts.filter(id__gt=last_visited_id)[:batch_size]:
                accounts_to_update = []

                with ThreadPoolExecutor(max_workers=threads) as executor:
                    future_to_account = {
                        executor.submit(self._call_api, account, retries=1): account
                        for account in chunk_of_bank_accounts
                    }

                    for future in as_completed(future_to_account):
                        account = future_to_account[future]
                        try:
                            iban_inquiry = future.result()
                            account.account_number = iban_inquiry.deposit_number
                            accounts_to_update.append(account)
                        except Exception as e:
                            report_exception()
                            failed_accounts.append(account.id)

                if accounts_to_update:
                    number_of_updated_objects += BankAccount.objects.bulk_update(accounts_to_update, ['account_number'])

                last_visited_id = max([a.id for a in chunk_of_bank_accounts])
                progress_bar.set_postfix(updated=number_of_updated_objects)
                progress_bar.update(len(chunk_of_bank_accounts))

                if len(chunk_of_bank_accounts) < batch_size:
                    break

        self.stdout.write(self.style.ERROR(f'failed BankAccount ids: {failed_accounts}'))

    def _call_api(self, account, retries: int = 2) -> IbanInquiry:
        if retries < 0:
            raise Exception('service connection error')
        try:
            return JibitVerificationClient().iban_inquery(account.shaba_number)
        except (requests.Timeout, requests.ConnectionError):
            sleep(1)
            return self._call_api(account, retries - 1)
