import os
from decimal import Decimal

import openpyxl
from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.accounts.models import Notification, User
from exchange.base.models import Currencies
from exchange.wallet.models import Transaction, Wallet


class Command(BaseCommand):
    help = 'Deposit Toncoin giveaways to Hamster pre-launch campaign'

    deposit_transaction_description = 'واریز جایزه کمپین ثبت‌نام پیش از لانچ همستر'
    withdraw_transaction_description = 'برداشت جایزه کمپین ثبت‌نام پیش از لانچ همستر'
    src_transaction_ref_module = Transaction.REF_MODULES['CampaignGiveawayHamsterPreLaunchSrc']
    dst_transaction_ref_module = Transaction.REF_MODULES['CampaignGiveawayHamsterPreLaunchDst']
    currency = Currencies.ton
    source_user = None
    source_user_username = 'financial@nobitex.ir'
    num_rows_processed = 0
    num_rows_already_processed = 0
    giveaway_amount = Decimal(1)

    def add_arguments(self, parser):
        parser.add_argument('excel_file', type=str, help='Path to the Excel file')

    def handle(self, *args, **kwargs):
        excel_file = kwargs['excel_file']
        if not os.path.exists(excel_file):
            self.stdout.write(self.style.ERROR(f'No such excel file: {excel_file}'))
            return

        workbook = openpyxl.load_workbook(excel_file, data_only=True)
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=False, max_col=2)

        self.source_user = User.objects.filter(username=self.source_user_username).first()
        if not self.source_user:
            self.stdout.write(self.style.ERROR('The source user not found!'))
            return

        for row in rows:
            try:
                user_id_row, status_row = row
                if not user_id_row:
                    continue
                user_id = user_id_row.value
                status = status_row.value if status_row else 'NotProcessed'

                if status == 'Processed':
                    self.stdout.write(
                        msg=f'Skipping already processed record for user_id="{user_id}"',
                    )
                    self.num_rows_already_processed += 1
                    continue

                with transaction.atomic():
                    user = User.objects.filter(webengage_cuid=user_id, is_active=True).first()
                    if not user:
                        status_row.value = 'UserNotFound'
                        workbook.save(excel_file)
                        continue

                    # Create a withdrawal transaction
                    _withdraw_transaction = self.create_and_commit_transaction(
                        user=self.source_user,
                        amount=Decimal(-self.giveaway_amount),
                    )
                    # Create a deposit transaction
                    _deposit_transaction = self.create_and_commit_transaction(
                        user=user, amount=Decimal(self.giveaway_amount)
                    )

                    _notification = self.send_message(user=user)

                    # Mark the Excel row as processed
                    status_row.value = 'Processed'

                    # Print the transaction details
                    success_text = (
                        f'Processed transaction for user={user.username}, webengage_id={user_id}, '
                        f'amount={self.giveaway_amount}TON, '
                        f'transaction_id={_deposit_transaction.id}'
                    )
                    if _notification:
                        success_text = f'{success_text}, notification_id={_notification.id}'
                    self.stdout.write(success_text)
                    self.num_rows_processed += 1

                    workbook.save(excel_file)

            except ValueError as e:
                if str(e).startswith('SourceWallet'):
                    self.stdout.write(self.style.ERROR('Insufficient the source wallet balance'))
                    return
                self.stdout.write(self.style.ERROR(f'User wallet user_id={user_id} has a problem: {e}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'An error occurred for user_id={user_id}: {e}'))

        self.stdout.write(
            self.style.SUCCESS(
                f'All records processed!\nprocessed {self.num_rows_processed} rows '
                f'and {self.num_rows_already_processed} are already processed.',
            ),
        )

    def create_and_commit_transaction(self, user: User, amount: Decimal) -> Transaction:
        wallet = Wallet.get_user_wallet(user=user, currency=self.currency)

        transaction_ref_module = self.dst_transaction_ref_module
        transaction_tp = 'deposit'
        insufficient_balance_error_prefix = 'UserWallet'
        transaction_description = self.withdraw_transaction_description
        if user == self.source_user:
            transaction_ref_module = self.src_transaction_ref_module
            transaction_tp = 'withdraw'
            insufficient_balance_error_prefix = 'SourceWallet'
            transaction_description = self.deposit_transaction_description

        if wallet.active_balance + amount < 0:
            raise ValueError(f'{insufficient_balance_error_prefix}InsufficientBalance')

        _transaction = wallet.create_transaction(
            tp=transaction_tp,
            amount=amount,
            description=transaction_description,
        )

        if _transaction is None:
            raise ValueError('InsufficientBalanceOrInactiveWallet')

        ref_id = user.id if user != self.source_user else _transaction.id
        _transaction.commit(ref=Transaction.Ref(ref_module=transaction_ref_module, ref_id=ref_id))
        return _transaction

    def send_message(self, user: User):
        return Notification.objects.create(
            user=user,
            message='کاربر گرامی، جایزه گوش‌به‌زنگ شما در نوبیتکس به میزان 1 تون‌کوین'
            ' (TON) '
            'به کیف پول نوبیتکس شما واریز شد.\n'
            'می‌توانید برای واریز آن به تون‌کیپر اقدام کنید.',
        )
