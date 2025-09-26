import os

import openpyxl
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from tqdm import tqdm

from exchange.accounts.models import BankAccount
from exchange.features.models import QueueItem
from exchange.shetab.models import JibitAccount, JibitPaymentId


class IDepositGeneralError(Exception):
    pass


class Command(BaseCommand):
    help = 'Add JibitPaymentId for VIP users manually - IDeposit feature'

    error_messages = []
    num_rows_processed = 0
    num_rows_already_processed = 0
    num_rows_had_error = 0
    num_rows_failed = 0
    feature_key = QueueItem.FEATURES.nobitex_jibit_ideposit

    def add_arguments(self, parser):
        parser.add_argument('excel_file', type=str, help='Path to the Excel file')
        parser.add_argument(
            '--retry-failed',
            help='Do you want to retry the rows that previously failed?',
            action='store_true',
        )

    def handle(self, *args, **kwargs):
        retry_failed_rows = kwargs['retry_failed']
        nobitex_jibit_account, _ = JibitAccount.objects.get_or_create(
            bank=JibitAccount.BANK_CHOICES.BKMTIR,
            iban='IR760120000000007565000016',
            defaults={
                'account_number': '7565000016',
                'owner_name': 'راهکار فناوری نویان',
                'account_type': JibitAccount.ACCOUNT_TYPES.nobitex_jibit,
            },
        )

        excel_file = kwargs['excel_file']
        if not os.path.exists(excel_file):
            self.stdout.write(self.style.ERROR(f'No such excel file: {excel_file}'))
            return

        workbook = openpyxl.load_workbook(excel_file, data_only=True)
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=False, min_row=2, max_col=5)
        try:
            for index, row in tqdm(enumerate(rows)):
                (
                    reference_number_cell,
                    pay_id_cell,
                    destination_iban_cell,
                    destination_account_cell,
                    status_cell,
                ) = row

                if not (pay_id_cell and reference_number_cell and pay_id_cell.value and reference_number_cell.value):
                    continue
                try:
                    reference_number = str(reference_number_cell.value)
                    try:
                        user_payment_id = str(int(pay_id_cell.value))
                    except ValueError:
                        continue
                    nobitex_iban = str(destination_iban_cell.value)
                    try:
                        nobitex_account = str(int(destination_account_cell.value))
                    except ValueError:
                        raise IDepositGeneralError('DestinationAccountNotMatched')
                    status = str(status_cell.value) if status_cell.value else 'NotProcessed'

                    if status == 'Processed':
                        self.num_rows_already_processed += 1
                        continue

                    if status != 'NotProcessed' and not retry_failed_rows:
                        self.num_rows_had_error += 1
                        continue

                    if (
                        nobitex_jibit_account.iban != nobitex_iban
                        or nobitex_jibit_account.account_number != nobitex_account
                    ):
                        raise IDepositGeneralError('DestinationAccountNotMatched')

                    try:
                        bank_account = BankAccount.objects.get(
                            id=self.parse_bank_account_id(reference_number),
                            confirmed=True,
                        )
                    except BankAccount.DoesNotExist:
                        raise IDepositGeneralError('BankAccountNotFound')
                    except ValueError:
                        raise IDepositGeneralError('ReferenceNumberInvalid')

                    with transaction.atomic():
                        # activate flag for user
                        try:
                            queue_item, _ = QueueItem.objects.get_or_create(
                                feature=self.feature_key, user=bank_account.user
                            )
                            queue_item.enable_feature()
                        except Exception as e:
                            self.error_messages.append(f'An error occurred: {e}')
                            raise IDepositGeneralError('CantActivateFeatureFlag')

                        # create JibitPaymentId
                        try:
                            JibitPaymentId.objects.get_or_create(
                                bank_account=bank_account,
                                jibit_account=nobitex_jibit_account,
                                payment_id=user_payment_id,
                            )
                            self.num_rows_processed += 1
                            status_cell.value = 'Processed'
                            workbook.save(excel_file)
                        except IntegrityError:
                            raise IDepositGeneralError('AlreadyExist')
                        except Exception as e:
                            raise IDepositGeneralError(str(e))

                except IDepositGeneralError as e:
                    status_cell.value = str(e)
                    workbook.save(excel_file)
                    self.num_rows_failed += 1
                except Exception as e:
                    self.error_messages.append(f'An error occurred: {e}')

            for error in self.error_messages:
                self.stdout.write(self.style.ERROR(error))
            self.stdout.write(
                self.style.SUCCESS(
                    f'All records processed!\n'
                    f'processed {self.num_rows_processed} rows successfully\n'
                    f'{self.num_rows_already_processed} rows are already processed\n'
                    f'{self.num_rows_failed} rows had issues\n'
                    f'{self.num_rows_had_error} rows skipped, previously failed.'
                ),
            )
        finally:
            workbook.close()

    def parse_bank_account_id(self, reference_number: str) -> int:
        return int(reference_number[2:])
