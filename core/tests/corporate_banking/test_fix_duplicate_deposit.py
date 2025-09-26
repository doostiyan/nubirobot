import datetime
import io
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import BankAccount, User
from exchange.base.constants import MAX_32_INT
from exchange.corporate_banking.models import CoBankStatement, CoBankUserDeposit
from exchange.corporate_banking.models.bank_account import CoBankAccount
from exchange.corporate_banking.models.constants import ACCOUNT_TP, NOBITEX_BANK_CHOICES, STATEMENT_TYPE
from exchange.system.models import ir_dst
from exchange.wallet.deposit import Currencies
from exchange.wallet.models import Transaction, Wallet


class CoBankFixDuplicateDepositTest(TestCase):
    def setUp(self):
        self.bank_account = CoBankAccount.objects.create(
            provider_bank_id=11,
            bank=NOBITEX_BANK_CHOICES.saman,
            iban='IR999999999999999999999991',
            account_number='10.8593617.1',
            account_owner='راهکار فناوری نویان',
            is_active=True,
            account_tp=ACCOUNT_TP.operational,
            is_deleted=False,
        )
        self.user_bank_account = BankAccount.objects.create(
            user_id=201,
            account_number='SRC-9876',
            shaba_number='IR500190000000218005998002',
            owner_name='asd',
            bank_name='something',
            bank_id=BankAccount.BANK_ID.saderat,
            confirmed=True,
        )

        self.wallet = Wallet.get_user_wallet(user=201, currency=Currencies.rls)

        self.statement = CoBankStatement.objects.create(
            amount=Decimal('10000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-001',
            source_account='SRC.9876',
            destination_account=self.bank_account,
            transaction_datetime=datetime.datetime.now(ir_dst),
        )

        self.deposit = CoBankUserDeposit.objects.create(
            cobank_statement=self.statement,
            user_id=201,
            user_bank_account=self.user_bank_account,
            amount=self.statement.amount,
        )

    def test_handle_creates_reverse_transaction_for_duplicate_deposit(self):
        duplicate_statement = CoBankStatement.objects.create(
            amount=Decimal('10000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-001',
            source_account='SRC.9876',
            destination_account=self.bank_account,
            transaction_datetime=datetime.datetime.now(ir_dst),
        )

        dup_deposit = CoBankUserDeposit.objects.create(
            cobank_statement=duplicate_statement,
            user_id=201,
            user_bank_account=self.user_bank_account,
            amount=duplicate_statement.amount,
        )

        duplicate_statement_not_executed = CoBankStatement.objects.create(
            amount=Decimal('10000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-001',
            source_account='SRC.9876',
            destination_account=self.bank_account,
            transaction_datetime=datetime.datetime.now(ir_dst),
        )

        assert CoBankUserDeposit.objects.all().count() == 2
        self.wallet.refresh_from_db()
        assert self.wallet.balance == dup_deposit.transaction.amount * 2

        output = io.StringIO()
        sys.stdout = output
        call_command('fix_cobank_duplicate_deposits')
        sys.stdout = sys.__stdout__

        self.wallet.refresh_from_db()
        assert self.wallet.balance == dup_deposit.transaction.amount

        ref_id = (
            hash(
                ','.join(
                    [
                        str(dup_deposit.transaction.amount),
                        dup_deposit.cobank_statement.tracing_number,
                        dup_deposit.cobank_statement.source_account,
                    ]
                )
            )
            % MAX_32_INT
        ) - 1

        ref_module = Transaction.REF_MODULES['ReverseTransaction']
        tx = Transaction.objects.filter(
            wallet=self.wallet,
            tp=Transaction.TYPE.manual,
            ref_module=ref_module,
            ref_id=ref_id,
        ).first()

        assert tx is not None
        assert tx.description == f'کسر بابت واریز دابل اسپند کوبنک رسالت شناسه {dup_deposit.id} با شماره پیگیری TRX-001'

        assert output.getvalue().split('\n')[3] == "['TRX-001']"
