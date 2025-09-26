from typing import ClassVar

from django.core.management.base import BaseCommand
from tqdm import tqdm

from exchange.accounts.constants import ACCOUNT_NUMBER_PATTERN_RE
from exchange.accounts.models import BankAccount
from exchange.base.logging import report_exception


class Command(BaseCommand):
    help = 'Fill account numbers'
    test_account_emails: ClassVar = [  # TODO: MAT - Remove it in future
        'm.a.taqvazadeh@gmail.com',
        'del.mirfendereski@gmail.com',
        'mehdi.shah.moh@gmail.com',
        'zahrafarahany21@gmail.com',
        'fatahzade@gmail.com',
        'rzi.babaee@gmail.com',
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            '-b',
            type=int,
            default=100,
            help='Specify the batch size for processing (default: 100)',
        )
        parser.add_argument(
            '--stop-on-error',
            '-s',
            action='store_true',
            help='Stop processing on the first error encountered',
        )
        parser.add_argument(
            '--test',
            '-t',
            action='store_true',
            help='Run command on test accounts only',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        stop_on_error = options['stop_on_error']
        self.stdout.write(self.style.SUCCESS(f'Starting to fill account numbers with bulk size: {batch_size}'))

        bank_accounts = BankAccount.objects.filter(
            is_deleted=False,
            account_number__in=['0', ''],
            api_verification__isnull=False,
            confirmed=True,
        ).order_by('id')

        test_mode = options['test']
        if test_mode:
            bank_accounts = bank_accounts.filter(user__email__in=self.test_account_emails)
            self.stdout.write(self.style.SUCCESS('Running in test mode'))

        if not bank_accounts.exists():
            self.stdout.write(self.style.SUCCESS('No records to update'))
            return

        total_updated_records = 0
        with tqdm(total=bank_accounts.count()) as progress_bar:
            last_visited_id = -1
            while chunk_of_bank_accounts := bank_accounts.filter(id__gt=last_visited_id)[:batch_size]:
                accounts_to_update = []
                for account in chunk_of_bank_accounts:
                    try:
                        verification_api = account.get_api_verification_as_dict()
                        if (
                            verification_api
                            and verification_api.get('result')
                            and verification_api['result'].get('deposit')
                            and ACCOUNT_NUMBER_PATTERN_RE.match(verification_api['result']['deposit'].strip())
                        ):
                            # Finnotech
                            account.account_number = verification_api['result']['deposit'].strip()
                            accounts_to_update.append(account)
                        elif (
                            verification_api
                            and verification_api.get('ibanInfo')
                            and verification_api['ibanInfo'].get('depositNumber')
                            and ACCOUNT_NUMBER_PATTERN_RE.match(verification_api['ibanInfo']['depositNumber'].strip())
                        ):
                            # Jibit
                            account.account_number = verification_api['ibanInfo']['depositNumber'].strip()
                            accounts_to_update.append(account)
                    except Exception as e:
                        self.stderr.write(self.style.ERROR(f'Error processing account ID {account.id}: {e}'))
                        report_exception()
                        if stop_on_error:
                            self.stdout.write(self.style.ERROR('Stopping due to error as requested.'))
                            return
                    finally:
                        last_visited_id = account.id

                if accounts_to_update:
                    total_updated_records += BankAccount.objects.bulk_update(accounts_to_update, ['account_number'])

                progress_bar.set_postfix(updated=total_updated_records)
                progress_bar.update(len(chunk_of_bank_accounts))

                if len(chunk_of_bank_accounts) < batch_size:
                    break

        self.stdout.write(self.style.SUCCESS(f'Successfully filled {total_updated_records} account numbers'))
