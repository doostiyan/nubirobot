import os

import openpyxl
from django.core.management.base import BaseCommand
from django.db import transaction
from tqdm import tqdm

from exchange.base.constants import MAX_32_INT
from exchange.base.models import Currencies
from exchange.corporate_banking.models import STATEMENT_STATUS, CoBankStatement
from exchange.corporate_banking.models.constants import STATEMENT_TYPE
from exchange.wallet.deposit import Currencies
from exchange.wallet.models import Transaction, Wallet


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('excel_file', type=str, help='Path to the Excel file')
        parser.add_argument('--dry-run', action='store_true', default=False)

    def handle(self, *args, dry_run, **kwargs):
        excel_file = kwargs['excel_file']
        if not os.path.exists(excel_file):
            self.stdout.write(self.style.ERROR(f'No such excel file: {excel_file}'))
            return

        invalid_statements = []
        reverted_txs = 0

        workbook = openpyxl.load_workbook(excel_file, data_only=True)
        sheet = workbook.active

        for row in tqdm(sheet.iter_rows()):
            if self.is_header_row(row):
                continue

            if row[6] == 'FALSE':
                continue

            statement_id = int(row[4].value)
            statement = CoBankStatement.objects.filter(
                provider_statement_id=statement_id,
                destination_account__account_number='47001700250602',
                status=STATEMENT_STATUS.executed,
                tp=STATEMENT_TYPE.deposit,
            )

            if len(statement) != 1:
                invalid_statements.append(statement_id)
                continue

            statement = statement[0]
            deposit = statement.deposit
            wallet = Wallet.get_user_wallet(user=deposit.user, currency=Currencies.rls)
            ref_id = (
                hash(
                    ','.join(
                        [
                            str(deposit.transaction.amount),
                            statement.provider_statement_id,
                            statement.tracing_number,
                            statement.source_account,
                        ]
                    )
                )
                % MAX_32_INT
            ) - 1

            ref_module = Transaction.REF_MODULES['ReverseTransaction']

            if not dry_run:
                with transaction.atomic():
                    tx = wallet.create_transaction(
                        tp='manual',
                        amount=-deposit.transaction.amount,
                        ref_id=ref_id,
                        ref_module=ref_module,
                        allow_negative_balance=True,
                        description=f'کسر بابت واریز دابل اسپند کوبنک پارسیان شناسه {deposit.id} با شماره پیگیری {statement.tracing_number}',
                    )
                    tx.commit(allow_negative_balance=True)
                reverted_txs += 1

        print(f'invalid/not-duplicate statement: {invalid_statements}')
        print(f'Total reverted deposits: {reverted_txs}')

    def is_header_row(self, row):
        try:
            int(row[1].value)
            return False
        except (ValueError, TypeError):
            return True
