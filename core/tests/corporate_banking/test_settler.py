import random
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

import pytest
from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import BankAccount, Notification, User, UserSms
from exchange.base.calendar import ir_now
from exchange.base.models import RIAL
from exchange.corporate_banking.models import (
    ACCOUNT_TP,
    NOBITEX_BANK_CHOICES,
    REJECTION_REASONS,
    STATEMENT_STATUS,
    STATEMENT_TYPE,
    CoBankAccount,
    CoBankStatement,
    CoBankUserDeposit,
)
from exchange.corporate_banking.services.settler import Settler
from exchange.corporate_banking.services.validators import (
    BankAccountValidator,
    DepositAmountValidator,
    DoubleSpendPreventer,
)
from exchange.features.models import QueueItem
from exchange.wallet.models import Transaction, Wallet


class TestSettler(TestCase):
    def setUp(self):
        self.settler = Settler()

        self.user = User.objects.create(
            username=f'alice_{random.randint(0, 1000000)}',
            user_type=User.USER_TYPE_LEVEL1,
            mobile='09121234567',
        )
        self.user_bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='SRC-9876',
            shaba_number='IR500190000000218005998002',
            owner_name=self.user.username,
            bank_name='something',
            bank_id=BankAccount.BANK_ID.saderat,
            confirmed=True,
        )
        self.cobank_operational_account = CoBankAccount.objects.create(
            provider_bank_id=4,
            bank=NOBITEX_BANK_CHOICES.saderat,
            iban='IR999999999999999999999992',
            account_number='OPER-1234',
            account_tp=ACCOUNT_TP.operational,
        )
        QueueItem.objects.create(user=self.user, feature=QueueItem.FEATURES.cobank, status=QueueItem.STATUS.done)

        self.deposit_statement = CoBankStatement.objects.create(
            amount=Decimal('10000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-001',
            source_iban='IR500190000000218005998002',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.new,
            transaction_datetime=ir_now() - timedelta(hours=1),
        )

    # --------------------------------------------------
    # TESTS FOR INDIVIDUAL METHODS
    # --------------------------------------------------
    @patch('exchange.corporate_banking.services.validators.Validator.validate', new_callable=MagicMock)
    def test_examine_deposit(self, mock_validate):
        """
        If the validator.validate does not raise any exceptions, we expect (validated, None).
        """
        mock_validate.return_value = None  # Means success
        state, reason = self.settler.examine_deposit(self.settler._get_validators(), self.deposit_statement)
        assert state == STATEMENT_STATUS.validated
        assert reason is None

    @patch('exchange.corporate_banking.services.validators.Validator.validate', new_callable=MagicMock)
    def test_examine_deposit_amount_exception(self, mock_validate):
        """
        If DepositAmountValidator.error is raised, return (rejected, unacceptable_amount).
        """
        mock_validate.side_effect = DepositAmountValidator.error('AmountTooLow')
        state, reason = self.settler.examine_deposit(self.settler._get_validators(), self.deposit_statement)
        assert state == STATEMENT_STATUS.rejected
        assert reason == REJECTION_REASONS.unacceptable_amount

    @patch('exchange.corporate_banking.services.validators.Validator.validate', new_callable=MagicMock)
    def test_examine_deposit_bank_account_exception(self, mock_validate):
        """
        If BankAccountValidator.error is raised with code='SharedBankAccount',
        we expect (rejected, shared_source_account).
        """
        mock_validate.side_effect = BankAccountValidator.error('SharedBankAccount')
        state, reason = self.settler.examine_deposit(self.settler._get_validators(), self.deposit_statement)
        assert state == STATEMENT_STATUS.rejected
        assert reason == REJECTION_REASONS.shared_source_account

    @patch('exchange.corporate_banking.services.validators.Validator.validate', new_callable=MagicMock)
    def test_examine_deposit_double_spend_repeated_reference_code(self, mock_validate):
        """
        If DoubleSpendPreventer.error is raised with code='RepeatedReferenceCode',
        we expect (pending_admin, repeated_reference_code).
        """
        mock_validate.side_effect = DoubleSpendPreventer.error('RepeatedReferenceCode')
        state, reason = self.settler.examine_deposit(self.settler._get_validators(), self.deposit_statement)
        assert state == STATEMENT_STATUS.pending_admin
        assert reason == REJECTION_REASONS.repeated_reference_code

    @patch('exchange.corporate_banking.services.validators.Validator.validate', new_callable=MagicMock)
    def test_examine_deposit_other_exception(self, mock_validate):
        """
        If any other exception occurs, we get (rejected, other).
        """
        mock_validate.side_effect = Exception('Unexpected')
        state, reason = self.settler.examine_deposit(self.settler._get_validators(), self.deposit_statement)
        assert state == STATEMENT_STATUS.rejected
        assert reason == REJECTION_REASONS.other

    # -----------------------------
    # test_validate_deposits
    # -----------------------------
    @patch.object(Settler, 'examine_deposit')
    def test_validate_deposits(self, mock_examine):
        """
        If examine_deposit returns different statuses, we check how the statements are updated.
        """
        s1 = CoBankStatement.objects.create(
            amount=Decimal('1000'),
            tp=STATEMENT_TYPE.deposit,
            status=STATEMENT_STATUS.new,
            source_account='SRC-1',
            destination_account=self.cobank_operational_account,
        )
        s2 = CoBankStatement.objects.create(
            amount=Decimal('2000'),
            tp=STATEMENT_TYPE.deposit,
            status=STATEMENT_STATUS.new,
            source_account='SRC-2',
            destination_account=self.cobank_operational_account,
        )
        s3 = CoBankStatement.objects.create(
            amount=Decimal('3000'),
            tp=STATEMENT_TYPE.deposit,
            status=STATEMENT_STATUS.new,
            source_account='SRC-3',
            destination_account=self.cobank_operational_account,
        )

        # mock_examine will return different statuses for each deposit: valid, pending_admin, rejected
        mock_examine.side_effect = [
            (STATEMENT_STATUS.validated, None),
            (STATEMENT_STATUS.pending_admin, None),
            (STATEMENT_STATUS.rejected, REJECTION_REASONS.unacceptable_amount),
        ]

        result = self.settler.validate_deposits(CoBankStatement.objects.filter(pk__in=[s1.pk, s2.pk, s3.pk]))

        # We expect s1 to be in 'valid_statements'
        # s2 => pending_admin => status should be updated to STATEMENT_STATUS.pending_admin
        # s3 => rejected => we set status=rejected, reason=unacceptable_amount
        assert len(result) == 1
        assert result[0].pk == s1.pk

        s3.refresh_from_db()
        assert s3.status == STATEMENT_STATUS.rejected
        assert s3.rejection_reason == REJECTION_REASONS.unacceptable_amount

        s2.refresh_from_db()
        assert s2.status == STATEMENT_STATUS.pending_admin

    @patch(
        'django.conf.settings.NOBITEX_OPTIONS',
        {'coBankLimits': {'maxDeposit': 10000, 'minDeposit': 500}, 'coBankFee': {'rate': Decimal('0.0001')}},
    )
    def test_validate_deposits_bypass_high_amount(self):
        """
        If bypass_high_amount is True, amounts more than maximum are handled. Other cases are unaffected.
        """
        low_amount_statement = CoBankStatement.objects.create(
            amount=Decimal('10'),
            tp=STATEMENT_TYPE.deposit,
            status=STATEMENT_STATUS.new,
            source_iban=self.user_bank_account.shaba_number,
            destination_account=self.cobank_operational_account,
        )
        acceptable_amount_statement = CoBankStatement.objects.create(
            amount=Decimal('2000'),
            tp=STATEMENT_TYPE.deposit,
            status=STATEMENT_STATUS.new,
            source_iban=self.user_bank_account.shaba_number,
            destination_account=self.cobank_operational_account,
        )
        high_amount_statement = CoBankStatement.objects.create(
            amount=Decimal('10000') + 10,
            tp=STATEMENT_TYPE.deposit,
            status=STATEMENT_STATUS.new,
            source_iban=self.user_bank_account.shaba_number,
            destination_account=self.cobank_operational_account,
        )

        result = self.settler.validate_deposits(
            [low_amount_statement, acceptable_amount_statement, high_amount_statement],
            bypass_high_amount=True,
        )

        # We expect low_amount_statement to be in 'rejected' because of unacceptable_amount
        # acceptable_amount_statement => validated
        # high_amount_statement => validated
        assert len(result) == 2
        assert {result[0].pk, result[1].pk} == {acceptable_amount_statement.pk, high_amount_statement.pk}

        low_amount_statement.refresh_from_db()
        assert low_amount_statement.status == STATEMENT_STATUS.rejected
        assert low_amount_statement.rejection_reason == REJECTION_REASONS.unacceptable_amount

    @patch(
        'django.conf.settings.NOBITEX_OPTIONS',
        {'coBankLimits': {'maxDeposit': 10000, 'minDeposit': 500}, 'coBankFee': {'rate': Decimal('0.0001')}},
    )
    def test_validate_deposits_ignore_double_spend(self):
        """
        If ignore_double_spend is True, cases of possible double spend are ignored.
        """
        double_spend_by_repeated_reference_statement = CoBankStatement.objects.create(
            amount=self.deposit_statement.amount,
            tp=STATEMENT_TYPE.deposit,
            status=STATEMENT_STATUS.new,
            source_iban=self.deposit_statement.source_iban,
            destination_account=self.deposit_statement.destination_account,
            tracing_number=self.deposit_statement.tracing_number,
        )
        double_spend_by_old_transaction_statement = CoBankStatement.objects.create(
            amount=self.deposit_statement.amount,
            tp=STATEMENT_TYPE.deposit,
            status=STATEMENT_STATUS.new,
            source_iban=self.deposit_statement.source_iban,
            destination_account=self.deposit_statement.destination_account,
            tracing_number=self.deposit_statement.tracing_number + '_2',
            transaction_datetime=ir_now() - timedelta(hours=48, seconds=1),
        )

        result = self.settler.validate_deposits(
            [double_spend_by_repeated_reference_statement, double_spend_by_old_transaction_statement],
            ignore_double_spend=True,
        )

        # We expect both statement to be validated
        assert len(result) == 2
        assert {result[0].pk, result[1].pk} == {
            double_spend_by_repeated_reference_statement.pk,
            double_spend_by_old_transaction_statement.pk,
        }

    @patch(
        'django.conf.settings.NOBITEX_OPTIONS',
        {'coBankLimits': {'maxDeposit': 10000, 'minDeposit': 500}, 'coBankFee': {'rate': Decimal('0.0001')}},
    )
    def test_validate_deposits_detect_double_spend_after_previous_rejection_reason_was_resolved(self):
        """
        When a statement encounters one rejection reason which is resolved later, when we want to re-evaluate it
        we still have to check if for other errors e.g. double spend.
        """
        double_spend_by_repeated_reference_statement = CoBankStatement.objects.create(
            amount=self.deposit_statement.amount,
            tp=STATEMENT_TYPE.deposit,
            status=STATEMENT_STATUS.new,
            source_iban=self.deposit_statement.source_iban,
            destination_account=self.deposit_statement.destination_account,
            tracing_number=self.deposit_statement.tracing_number,
        )
        QueueItem.objects.all().delete()

        result = self.settler.validate_deposits([double_spend_by_repeated_reference_statement])

        # We expect the statement to be pending_admin for lack of feature flag
        assert len(result) == 0
        double_spend_by_repeated_reference_statement.refresh_from_db()
        assert double_spend_by_repeated_reference_statement.status == STATEMENT_STATUS.pending_admin
        assert double_spend_by_repeated_reference_statement.rejection_reason == REJECTION_REASONS.no_feature_flag

        # Resolve the previous error --> create feature flag
        QueueItem.objects.create(user=self.user, feature=QueueItem.FEATURES.cobank, status=QueueItem.STATUS.done)

        result = self.settler.validate_deposits([double_spend_by_repeated_reference_statement])

        # We expect the statement to be pending_admin for double spend suspicion
        assert len(result) == 0
        double_spend_by_repeated_reference_statement.refresh_from_db()
        assert double_spend_by_repeated_reference_statement.status == STATEMENT_STATUS.pending_admin
        assert (
            double_spend_by_repeated_reference_statement.rejection_reason == REJECTION_REASONS.repeated_reference_code
        )

    # -----------------------------
    # test_create_deposit
    # -----------------------------
    @patch('django.db.transaction.on_commit')
    def test_create_deposit_by_iban_successfully(self, mock_on_commit):
        """
        create_deposit should:
         - fetch the source iban
         - create CoBankUserDeposit
         - set statement.status=executed
         - schedule self.notify(deposit) in on_commit
        """
        self.deposit_statement.source_iban = self.user_bank_account.shaba_number
        self.deposit_statement.source_account = None
        self.deposit_statement.save()
        self.settler.create_deposit(self.deposit_statement)
        # After creation, the statement should be updated
        self.deposit_statement.refresh_from_db()
        assert self.deposit_statement.status == STATEMENT_STATUS.executed

        # A CoBankUserDeposit should be created
        deposit_obj = CoBankUserDeposit.objects.first()
        assert deposit_obj is not None
        assert deposit_obj.cobank_statement == self.deposit_statement
        assert deposit_obj.user_bank_account == self.user_bank_account
        assert deposit_obj.user == self.user
        assert deposit_obj.amount == Decimal('10000')
        assert deposit_obj.fee == Decimal('1')  # 10000 * 0.0001
        # The deposit object should have a Transaction
        assert deposit_obj.transaction is not None
        assert deposit_obj.transaction.amount == Decimal('9999')  # deposit_obj.amount - deposit_obj.fee
        assert deposit_obj.transaction.tp == Transaction.TYPE.deposit
        assert deposit_obj.transaction.ref_module == Transaction.REF_MODULES['CoBankDeposit']
        assert deposit_obj.transaction.ref_id == deposit_obj.cobank_statement.id
        assert deposit_obj.transaction.description == (
            'واریز حساب به حساب - شماره شبا: IR500190000000218005998002 - شماره رهگیری: TRX-001'
        )
        # The correct wallet should be charged
        assert deposit_obj.transaction.wallet.user == self.user
        assert deposit_obj.transaction.wallet.currency == RIAL
        assert deposit_obj.transaction.wallet.type == Wallet.WALLET_TYPE.spot
        assert deposit_obj.transaction.wallet.balance == Decimal('9999')
        # The on_commit callback is scheduled
        # first on_commit is in .save for fraud function
        # the second one is that one this test is looking for
        assert mock_on_commit.call_count == 2

    @patch('exchange.corporate_banking.models.deposit.create_and_commit_transaction', new_callable=MagicMock)
    @patch('django.db.transaction.on_commit')
    def test_create_no_deposit_without_transaction(self, mock_on_commit, mock_create_and_commit_transaction):
        """
        create_deposit should not create a CoBankUserDeposit without a valid transaction
        """

        mock_create_and_commit_transaction.side_effect = Exception('something went wrong')
        with self.assertRaises(Exception):
            self.settler.create_deposit(self.deposit_statement)
        # After creation, the statement should be updated
        self.deposit_statement.refresh_from_db()
        assert self.deposit_statement.status == STATEMENT_STATUS.new

        # A CoBankUserDeposit should be created
        assert CoBankUserDeposit.objects.first() is None
        assert Transaction.objects.first() is None
        assert Wallet.get_user_wallet(self.user, RIAL).balance == Decimal(0)
        assert mock_on_commit.call_count == 0

    @patch('django.db.transaction.on_commit')
    def test_create_no_deposit_without_transaction_when_amount_is_negative(self, mock_on_commit):
        self.deposit_statement.amount = -1000

        with pytest.raises(ValueError, match='Deposit amount should be positive'):
            self.settler.create_deposit(self.deposit_statement)

        self.deposit_statement.refresh_from_db()
        assert self.deposit_statement.status == STATEMENT_STATUS.new

        assert CoBankUserDeposit.objects.first() is None
        assert Transaction.objects.first() is None
        assert Wallet.get_user_wallet(self.user, RIAL).balance == Decimal(0)
        assert mock_on_commit.call_count == 0

    @patch('django.db.transaction.on_commit')
    def test_create_deposit_successfully_with_negative_balance(self, mock_on_commit):
        wallet = Wallet.get_user_wallet(self.user, RIAL)
        wallet.balance = -self.deposit_statement.amount - 999
        wallet.save()

        self.settler.create_deposit(self.deposit_statement)
        self.deposit_statement.refresh_from_db()
        assert self.deposit_statement.status == STATEMENT_STATUS.executed

        deposit_obj = CoBankUserDeposit.objects.first()
        assert deposit_obj is not None
        assert deposit_obj.cobank_statement == self.deposit_statement
        assert deposit_obj.user_bank_account == self.user_bank_account
        assert deposit_obj.user == self.user
        assert deposit_obj.amount == Decimal('10000')
        assert deposit_obj.fee == Decimal('1')

        assert deposit_obj.transaction is not None
        assert deposit_obj.transaction.amount == Decimal('9999')
        assert deposit_obj.transaction.tp == Transaction.TYPE.deposit
        assert deposit_obj.transaction.ref_module == Transaction.REF_MODULES['CoBankDeposit']
        assert deposit_obj.transaction.ref_id == deposit_obj.cobank_statement.id
        assert deposit_obj.transaction.description == (
            'واریز حساب به حساب - شماره شبا: IR500190000000218005998002 - شماره رهگیری: TRX-001'
        )

        assert deposit_obj.transaction.wallet.user == self.user
        assert deposit_obj.transaction.wallet.currency == RIAL
        assert deposit_obj.transaction.wallet.type == Wallet.WALLET_TYPE.spot
        assert deposit_obj.transaction.wallet.balance == Decimal('-1000')

        assert mock_on_commit.call_count == 2

    # -----------------------------
    # test_notify
    # -----------------------------
    def test_notify_both_sms_and_notification(self):
        """
        notify() => create a Notification, and possibly create a UserSms if mobile_confirmed
        """
        vp = self.user.get_verification_profile()
        vp.mobile_confirmed = True
        vp.save()

        deposit_obj = CoBankUserDeposit.objects.create(
            cobank_statement=self.deposit_statement,
            user=self.user,
            user_bank_account=self.user_bank_account,
            amount=Decimal('100_000_0'),
        )

        self.settler.notify(deposit_obj)

        # We expect a Notification to be created
        notification = Notification.objects.filter(message__contains='تومان').first()
        assert notification is not None
        assert notification.user == self.user
        assert notification.message == '100,000 تومان از مبداء بانک صادرات به کیف اسپات شما در نوبیتکس واریز شد.'
        # We also expect a UserSms
        sms = UserSms.objects.first()
        assert sms is not None
        assert sms.user == self.user
        assert sms.tp == UserSms.TYPES.cobank_deposit
        assert sms.template == UserSms.TEMPLATES.cobank_deposit
        assert notification.message == '100,000 تومان از مبداء بانک صادرات به کیف اسپات شما در نوبیتکس واریز شد.'

    def test_notify_send_only_notification(self):
        """
        notify() => create a Notification, and possibly create a UserSms if mobile_confirmed
        """

        deposit_obj = CoBankUserDeposit.objects.create(
            cobank_statement=self.deposit_statement,
            user=self.user,
            user_bank_account=self.user_bank_account,
            amount=Decimal('100_000_0'),
        )

        self.settler.notify(deposit_obj)

        # We expect a Notification to be created
        notification = Notification.objects.filter(message__contains='تومان').first()
        assert notification is not None
        assert notification.user == self.user
        assert notification.message == '100,000 تومان از مبداء بانک صادرات به کیف اسپات شما در نوبیتکس واریز شد.'
        # There won't be any sms because user has no verified mobile number
        sms = UserSms.objects.first()
        assert sms is None

    # -----------------------------
    # test_settle_statements
    # -----------------------------
    @patch.object(Settler, '_increase_deposit_metrics')
    @patch.object(Settler, '_log_deposit_lag_metric')
    @patch.object(Settler, 'validate_deposits')
    @patch.object(Settler, 'create_deposit')
    def test_settle_statements(self, mock_create_deposit, mock_validate_deposits, mock_lag, mock_metrics):
        """
        settle_statements => queries new deposit statements, calls validate_deposits => create_deposit for each valid
        """
        # Suppose validate_deposits returns a list with one statement
        another_user = User.objects.create_user(
            username=f'Bob{random.randint(0, 10000)}', user_type=User.USER_TYPE_LEVEL2
        )
        another_bank_account = BankAccount.objects.create(
            user=another_user,
            account_number='SRC-9875',
            shaba_number='IR500190000000218005998001',
            owner_name=another_user.username,
            bank_name='something',
            bank_id=BankAccount.BANK_ID.saderat,
            confirmed=True,
        )
        another_deposit_statement = CoBankStatement.objects.create(
            amount=Decimal('10000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-002',
            source_account='SRC-9875',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.new,
        )
        withdraw_deposit = CoBankStatement.objects.create(
            amount=Decimal('-10000'),
            tp=STATEMENT_TYPE.withdraw,
            tracing_number='TRX-003',
            source_account='SRC-9875',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.new,
        )

        mock_validate_deposits.return_value = [self.deposit_statement, another_deposit_statement]

        self.settler.settle_statements()

        mock_validate_deposits.assert_called_once()
        assert withdraw_deposit not in list(mock_validate_deposits.call_args[0][0])
        # check that create_deposit was called for deposit statements and not the withdraw one
        assert mock_create_deposit.call_count == 2
        assert {mock_create_deposit.call_args_list[0].args[0], mock_create_deposit.call_args_list[1].args[0]} == {
            self.deposit_statement,
            another_deposit_statement,
        }

    # --------------------------------------------------
    # TEST THE ENTIRE FLOW WITHOUT MOCKS
    # --------------------------------------------------
    @patch(
        'django.conf.settings.NOBITEX_OPTIONS',
        {'coBankLimits': {'maxDeposit': 10000, 'minDeposit': 500}, 'coBankFee': {'rate': Decimal('0.0001')}},
    )
    @patch('exchange.corporate_banking.services.settler.transaction.on_commit', new_callable=MagicMock)
    def test_entire_flow_for_new_deposits_no_mocks(self, mock_on_commit):
        def transaction_on_commit_mock(f):
            f()

        mock_on_commit.side_effect = transaction_on_commit_mock

        another_user = User.objects.create_user(
            username=f'Bob{random.randint(0, 10000)}', user_type=User.USER_TYPE_LEVEL2
        )
        QueueItem.objects.create(user=another_user, feature=QueueItem.FEATURES.cobank, status=QueueItem.STATUS.done)
        another_bank_account = BankAccount.objects.create(
            user=another_user,
            account_number='SRC-9875',
            shaba_number='IR500190000000218005998001',
            owner_name=another_user.username,
            bank_name='something',
            bank_id=BankAccount.BANK_ID.saderat,
            confirmed=True,
        )
        # Another duplicate deleted bank account
        BankAccount.objects.create(
            user=another_user,
            account_number=another_bank_account.account_number,
            shaba_number=another_bank_account.shaba_number,
            owner_name=another_user.username,
            bank_name=another_bank_account.bank_name,
            bank_id=BankAccount.BANK_ID.saderat,
            confirmed=True,
            is_deleted=True,
        )
        amount_too_high_deposit_statement = CoBankStatement.objects.create(
            amount=Decimal('1000000'),  # Amount too high
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-002',
            source_account='SRC-9875',
            source_iban='IR500190000000218005998001',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.new,
        )
        empty_source_iban_deposit_statement = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-003',
            source_iban='',  # Empty
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.new,
        )
        nonexistent_account_deposit_statement = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-004',
            source_iban='non_existent_iban',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.new,
        )
        withdraw_deposit = CoBankStatement.objects.create(
            amount=Decimal('-10000'),
            tp=STATEMENT_TYPE.withdraw,
            tracing_number='TRX-005',
            source_account='SRC-9875',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.new,
        )
        another_valid_deposit_statement = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            source_iban='IR500190000000218005998001',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.new,
            transaction_datetime=ir_now(),
        )

        shared_bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='SRM-1990',
            shaba_number='IR500190000022218005998001',
            owner_name=self.user.username,
            bank_name='something',
            bank_id=BankAccount.BANK_ID.saderat,
            confirmed=True,
        )

        # Another shared bank account
        BankAccount.objects.create(
            user=another_user,
            account_number=shared_bank_account.account_number,
            shaba_number=shared_bank_account.shaba_number,
            owner_name=another_user.username,
            bank_name=shared_bank_account.bank_name,
            bank_id=BankAccount.BANK_ID.saderat,
            confirmed=True,
            is_deleted=True,
        )

        deposit_with_shared_account = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-886',
            source_iban=shared_bank_account.shaba_number,
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.new,
            transaction_datetime=ir_now(),
        )

        user_without_feature_flag = User.objects.create_user(
            username=f'Charlie{random.randint(0, 10000)}', user_type=User.USER_TYPE_LEVEL2
        )
        user_without_feature_flag_bank_account = BankAccount.objects.create(
            user=user_without_feature_flag,
            account_number='SRC-9874',
            shaba_number='IR500190000000218005998000',
            owner_name=another_user.username,
            bank_name='something',
            bank_id=BankAccount.BANK_ID.saderat,
            confirmed=True,
        )
        no_feature_flag_deposit_statement = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-007',
            source_iban='IR500190000000218005998000',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.new,
        )

        ineligible_user = User.objects.create_user(
            username=f'Kafy{random.randint(0, 10000)}', user_type=User.USER_TYPES.level0
        )
        QueueItem.objects.create(user=ineligible_user, feature=QueueItem.FEATURES.cobank, status=QueueItem.STATUS.done)
        ineligible_user_bank_account = BankAccount.objects.create(
            user=ineligible_user,
            account_number='SRC-9873',
            shaba_number='IR500190000000218005998999',
            owner_name=ineligible_user.username,
            bank_name='something',
            bank_id=BankAccount.BANK_ID.saderat,
            confirmed=True,
        )
        ineligible_user_deposit_statement = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-008',
            source_iban='IR500190000000218005998999',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.new,
        )

        self.settler.settle_statements()

        # To avoid self.deposit_statement become a double-spend case too, we try to settle this deposit
        # after self.deposit_statement
        double_spend_by_repeated_reference_deposit = CoBankStatement.objects.create(
            amount=self.deposit_statement.amount,
            tp=STATEMENT_TYPE.deposit,
            tracing_number=self.deposit_statement.tracing_number,
            source_iban=self.deposit_statement.source_iban,
            destination_account=self.deposit_statement.destination_account,
            status=STATEMENT_STATUS.new,
        )
        double_spend_by_old_deposit = CoBankStatement.objects.create(
            amount=self.deposit_statement.amount,
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-009',
            source_iban=self.deposit_statement.source_iban,
            destination_account=self.deposit_statement.destination_account,
            status=STATEMENT_STATUS.new,
            transaction_datetime=ir_now() - timedelta(hours=48, seconds=1),
        )
        not_double_spend_deposit = CoBankStatement.objects.create(
            amount=self.deposit_statement.amount - 10,  # Different amount
            tp=STATEMENT_TYPE.deposit,
            tracing_number=self.deposit_statement.tracing_number,
            source_iban=self.deposit_statement.source_iban,
            destination_account=self.deposit_statement.destination_account,
            status=STATEMENT_STATUS.new,
        )

        self.settler.settle_statements()

        # All deposits should get the correct status and rejection_reason if applicable
        self.deposit_statement.refresh_from_db()
        assert self.deposit_statement.status == STATEMENT_STATUS.executed  # Valid statement
        assert self.deposit_statement.rejection_reason is None

        amount_too_high_deposit_statement.refresh_from_db()
        assert amount_too_high_deposit_statement.status == STATEMENT_STATUS.pending_admin
        assert amount_too_high_deposit_statement.rejection_reason == REJECTION_REASONS.unacceptable_amount

        empty_source_iban_deposit_statement.refresh_from_db()
        assert empty_source_iban_deposit_statement.status == STATEMENT_STATUS.new

        nonexistent_account_deposit_statement.refresh_from_db()
        assert nonexistent_account_deposit_statement.status == STATEMENT_STATUS.pending_admin
        assert nonexistent_account_deposit_statement.rejection_reason == REJECTION_REASONS.source_account_not_found

        withdraw_deposit.refresh_from_db()
        assert withdraw_deposit.status == STATEMENT_STATUS.new
        assert withdraw_deposit.rejection_reason is None

        another_valid_deposit_statement.refresh_from_db()
        assert another_valid_deposit_statement.status == STATEMENT_STATUS.executed
        assert another_valid_deposit_statement.rejection_reason is None

        deposit_with_shared_account.refresh_from_db()
        assert deposit_with_shared_account.status == STATEMENT_STATUS.rejected
        assert deposit_with_shared_account.rejection_reason == REJECTION_REASONS.shared_source_account

        no_feature_flag_deposit_statement.refresh_from_db()
        assert no_feature_flag_deposit_statement.status == STATEMENT_STATUS.pending_admin
        assert no_feature_flag_deposit_statement.rejection_reason == REJECTION_REASONS.no_feature_flag

        ineligible_user_deposit_statement.refresh_from_db()
        assert ineligible_user_deposit_statement.status == STATEMENT_STATUS.rejected
        assert ineligible_user_deposit_statement.rejection_reason == REJECTION_REASONS.ineligible_user

        double_spend_by_repeated_reference_deposit.refresh_from_db()
        assert double_spend_by_repeated_reference_deposit.status == STATEMENT_STATUS.pending_admin
        assert double_spend_by_repeated_reference_deposit.rejection_reason == REJECTION_REASONS.repeated_reference_code

        double_spend_by_old_deposit.refresh_from_db()
        assert double_spend_by_old_deposit.status == STATEMENT_STATUS.pending_admin
        assert double_spend_by_old_deposit.rejection_reason == REJECTION_REASONS.old_transaction

        not_double_spend_deposit.refresh_from_db()
        assert not_double_spend_deposit.status == STATEMENT_STATUS.executed
        assert not_double_spend_deposit.rejection_reason is None

        # Correct CoBankUserDeposit objects should be created
        assert (
            CoBankUserDeposit.objects.filter(
                cobank_statement=self.deposit_statement,
                amount=Decimal('10000'),
                fee=Decimal('1'),
                user=self.user,
                user_bank_account=self.user_bank_account,
                transaction__amount=Decimal('9999'),
            ).count()
            == 1
        )
        assert (
            CoBankUserDeposit.objects.filter(
                cobank_statement=another_valid_deposit_statement,
                amount=Decimal('500'),
                fee=Decimal('0'),
                user=another_user,
                user_bank_account=another_bank_account,
                transaction__amount=Decimal('500'),
            ).count()
            == 1
        )
        assert (
            CoBankUserDeposit.objects.filter(
                cobank_statement=not_double_spend_deposit,
                amount=Decimal('9990'),
                fee=Decimal('0'),
                user=self.user,
                user_bank_account=self.user_bank_account,
                transaction__amount=Decimal('9990'),
            ).count()
            == 1
        )
        assert (
            CoBankUserDeposit.objects.filter(
                cobank_statement__in=[
                    amount_too_high_deposit_statement,
                    empty_source_iban_deposit_statement,
                    nonexistent_account_deposit_statement,
                    withdraw_deposit,
                    no_feature_flag_deposit_statement,
                    deposit_with_shared_account,
                    double_spend_by_repeated_reference_deposit,
                    double_spend_by_old_deposit,
                ],
            ).count()
            == 0
        )

        assert CoBankUserDeposit.objects.all().count() == 3
        assert Transaction.objects.all().count() == 3

        # Two Notifications for cobank deposits should be created by the notify method
        assert Notification.objects.filter(message__contains='کیف اسپات شما در نوبیتکس واریز شد').count() == 3

        # Test Lag metrics
        assert cache.get('time_cobank_deposit_settlement_lag__saderat_avg') == 30 * 60  # 30 min delay

    @patch(
        'django.conf.settings.NOBITEX_OPTIONS',
        {
            'coBankLimits': {'maxDeposit': 10000, 'minDeposit': 500},
            'coBankFee': {'rate': Decimal('0.0001')},
            'userTypes': {
                40: 'سطح ۰',
                44: 'سطح ۱',
                45: 'تریدر',
                46: 'سطح ۲',
                90: 'سطح ۳',
            },
        },
    )
    @patch('exchange.corporate_banking.services.settler.transaction.on_commit', new_callable=MagicMock)
    def test_entire_flow_for_automatic_check_on_pending_deposits_no_mocks(self, mock_on_commit):
        """
        In this flow, we only settle deposits that are on pending status because of lack of feature flag,
        low user level, or nonexistent bank account.
        New deposits or other types should not be affected in this flow.
        """

        def transaction_on_commit_mock(f):
            f()

        mock_on_commit.side_effect = transaction_on_commit_mock

        # Statements that MIGHT be affected by automatic check on pending statuse
        another_user = User.objects.create_user(
            username=f'Bob{random.randint(0, 10000)}', user_type=User.USER_TYPE_LEVEL2
        )
        QueueItem.objects.create(user=another_user, feature=QueueItem.FEATURES.cobank, status=QueueItem.STATUS.done)
        unconfirmed_bank_account = BankAccount.objects.create(
            user=another_user,
            account_number='SRC-9875',
            shaba_number='IR500190000000218005998001',
            owner_name=another_user.username,
            bank_name='something',
            bank_id=BankAccount.BANK_ID.saderat,
            confirmed=False,
        )
        # A deleted bank account
        deleted_bank_account = BankAccount.objects.create(
            user=another_user,
            account_number='SRC-9874',
            shaba_number='IR500190000000218005998004',
            owner_name=another_user.username,
            bank_name='anything',
            bank_id=BankAccount.BANK_ID.saderat,
            confirmed=True,
            is_deleted=True,
        )
        deposit_on_unconfirmed_account = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            source_iban=unconfirmed_bank_account.shaba_number,
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.pending_admin,
            rejection_reason=REJECTION_REASONS.source_account_not_found,
        )
        deposit_on_deleted_account = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            source_iban=deleted_bank_account.shaba_number,
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.pending_admin,
            rejection_reason=REJECTION_REASONS.source_account_not_found,
        )
        nonexistent_iban_deposit_statement = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-004',
            source_iban='non_existent_iban',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.pending_admin,
            rejection_reason=REJECTION_REASONS.source_account_not_found,
        )
        user_without_feature_flag = User.objects.create_user(
            username=f'Charlie{random.randint(0, 10000)}', user_type=User.USER_TYPE_LEVEL2
        )
        user_without_feature_flag_bank_account = BankAccount.objects.create(
            user=user_without_feature_flag,
            account_number='SRC-9873',
            shaba_number='IR500190000000218005998003',
            owner_name=another_user.username,
            bank_name='something',
            bank_id=BankAccount.BANK_ID.saderat,
            confirmed=True,
        )
        no_feature_flag_deposit_statement = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-007',
            source_iban=user_without_feature_flag_bank_account.shaba_number,
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.pending_admin,
            rejection_reason=REJECTION_REASONS.no_feature_flag,
        )

        ineligible_user = User.objects.create_user(
            username=f'Kafy{random.randint(0, 10000)}', user_type=User.USER_TYPES.level0
        )
        QueueItem.objects.create(user=ineligible_user, feature=QueueItem.FEATURES.cobank, status=QueueItem.STATUS.done)
        ineligible_user_bank_account = BankAccount.objects.create(
            user=ineligible_user,
            account_number='SRC-9872',
            shaba_number='IR500190000000218005998999',
            owner_name=ineligible_user.username,
            bank_name='something',
            bank_id=BankAccount.BANK_ID.saderat,
            confirmed=True,
        )
        ineligible_user_deposit_statement = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-008',
            source_iban=ineligible_user_bank_account.shaba_number,
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.rejected,
            rejection_reason=REJECTION_REASONS.ineligible_user,
        )

        # Statements that WILL NOT be affected by automatic check on pending statuses
        amount_too_high_deposit_statement = CoBankStatement.objects.create(
            amount=Decimal('1000000'),  # Amount too high
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-002',
            source_iban='IR500190000000218005998001',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.pending_admin,
            rejection_reason=REJECTION_REASONS.unacceptable_amount,
        )
        empty_source_iban_deposit_statement = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-003',
            source_iban='',  # Empty
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.pending_admin,
            rejection_reason=REJECTION_REASONS.empty_source_account,
        )
        withdraw_deposit = CoBankStatement.objects.create(
            amount=Decimal('-10000'),
            tp=STATEMENT_TYPE.withdraw,
            tracing_number='TRX-005',
            source_iban='IR500190000000218005998001',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.new,
        )

        shared_bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='SRM-1990',
            shaba_number='IR500190000022218005998001',
            owner_name=self.user.username,
            bank_name='something',
            bank_id=BankAccount.BANK_ID.saderat,
            confirmed=True,
        )
        # Another shared bank account
        BankAccount.objects.create(
            user=another_user,
            account_number=shared_bank_account.account_number,
            shaba_number=shared_bank_account.shaba_number,
            owner_name=another_user.username,
            bank_name=shared_bank_account.bank_name,
            bank_id=BankAccount.BANK_ID.saderat,
            confirmed=True,
            is_deleted=True,
        )

        deposit_with_shared_account = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-886',
            source_iban=shared_bank_account.shaba_number,
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.rejected,
            rejection_reason=REJECTION_REASONS.shared_source_account,
        )

        # Status is rejected but reason is not ineligible_user
        rejected_deposit_statement = CoBankStatement.objects.create(
            amount=Decimal('10000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-337',
            source_iban='IR500190000000218005998001',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.rejected,
            rejection_reason=REJECTION_REASONS.source_account_not_found,
        )

        # ------------------------------------------------------------------
        # FIRST TIME CALLING settle_statements with settling_pending_deposits=True
        # ------------------------------------------------------------------

        # Only the status of deposit from deleted account should be changed here
        # because we still settle deposits from deleted accounts
        Settler(settling_pending_deposits=True).settle_statements()

        # We'll change the status but keep the reason for history purposes for now (can be changed in the future)
        deposit_on_deleted_account.refresh_from_db()
        assert deposit_on_deleted_account.status == STATEMENT_STATUS.executed
        assert deposit_on_deleted_account.rejection_reason == REJECTION_REASONS.source_account_not_found

        # The rest are unchanged
        self.deposit_statement.refresh_from_db()
        assert self.deposit_statement.status == STATEMENT_STATUS.new
        assert self.deposit_statement.rejection_reason is None

        deposit_on_unconfirmed_account.refresh_from_db()
        assert deposit_on_unconfirmed_account.status == STATEMENT_STATUS.pending_admin
        assert deposit_on_unconfirmed_account.rejection_reason == REJECTION_REASONS.source_account_not_found

        nonexistent_iban_deposit_statement.refresh_from_db()
        assert nonexistent_iban_deposit_statement.status == STATEMENT_STATUS.pending_admin
        assert nonexistent_iban_deposit_statement.rejection_reason == REJECTION_REASONS.source_account_not_found

        no_feature_flag_deposit_statement.refresh_from_db()
        assert no_feature_flag_deposit_statement.status == STATEMENT_STATUS.pending_admin
        assert no_feature_flag_deposit_statement.rejection_reason == REJECTION_REASONS.no_feature_flag

        ineligible_user_deposit_statement.refresh_from_db()
        assert ineligible_user_deposit_statement.status == STATEMENT_STATUS.rejected
        assert ineligible_user_deposit_statement.rejection_reason == REJECTION_REASONS.ineligible_user

        amount_too_high_deposit_statement.refresh_from_db()
        assert amount_too_high_deposit_statement.status == STATEMENT_STATUS.pending_admin
        assert amount_too_high_deposit_statement.rejection_reason == REJECTION_REASONS.unacceptable_amount

        empty_source_iban_deposit_statement.refresh_from_db()
        assert empty_source_iban_deposit_statement.status == STATEMENT_STATUS.pending_admin
        assert empty_source_iban_deposit_statement.rejection_reason == REJECTION_REASONS.empty_source_account

        withdraw_deposit.refresh_from_db()
        assert withdraw_deposit.status == STATEMENT_STATUS.new
        assert withdraw_deposit.rejection_reason is None

        deposit_with_shared_account.refresh_from_db()
        assert deposit_with_shared_account.status == STATEMENT_STATUS.rejected
        assert deposit_with_shared_account.rejection_reason == REJECTION_REASONS.shared_source_account

        rejected_deposit_statement.refresh_from_db()
        assert rejected_deposit_statement.status == STATEMENT_STATUS.rejected
        assert rejected_deposit_statement.rejection_reason == REJECTION_REASONS.source_account_not_found

        # ----------------------------------------------
        # CHANGING WHAT PREVIOUSLY MADE DEPOSITS PENDING
        # ----------------------------------------------

        # Now let's create the changes necessary for automatic check on pending or rejected cases
        unconfirmed_bank_account.confirmed = True
        unconfirmed_bank_account.save(update_fields=('confirmed',))

        QueueItem.objects.create(
            feature=QueueItem.FEATURES.cobank, status=QueueItem.STATUS.done, user=user_without_feature_flag
        )

        ineligible_user.user_type = User.USER_TYPE_LEVEL1
        ineligible_user.save(update_fields=('user_type',))

        # -------------------------------------------------------------------
        # SECOND TIME CALLING settle_statements with settling_pending_deposits=True
        # -------------------------------------------------------------------

        # The status of deposits from unconfirmed account, no feature flag, and ineligible user should be executed
        # We didn't make an account for nonexistent_iban_deposit_statement, so it should stay the same as before
        Settler(settling_pending_deposits=True).settle_statements()

        # Changed deposits from the second run
        deposit_on_unconfirmed_account.refresh_from_db()
        assert deposit_on_unconfirmed_account.status == STATEMENT_STATUS.executed
        assert deposit_on_unconfirmed_account.rejection_reason == REJECTION_REASONS.source_account_not_found

        no_feature_flag_deposit_statement.refresh_from_db()
        assert no_feature_flag_deposit_statement.status == STATEMENT_STATUS.executed
        assert no_feature_flag_deposit_statement.rejection_reason == REJECTION_REASONS.no_feature_flag

        ineligible_user_deposit_statement.refresh_from_db()
        assert ineligible_user_deposit_statement.status == STATEMENT_STATUS.executed
        assert ineligible_user_deposit_statement.rejection_reason == REJECTION_REASONS.ineligible_user

        # Deposits that did not change in the second run
        self.deposit_statement.refresh_from_db()
        assert self.deposit_statement.status == STATEMENT_STATUS.new
        assert self.deposit_statement.rejection_reason is None

        nonexistent_iban_deposit_statement.refresh_from_db()
        assert nonexistent_iban_deposit_statement.status == STATEMENT_STATUS.pending_admin
        assert nonexistent_iban_deposit_statement.rejection_reason == REJECTION_REASONS.source_account_not_found

        deposit_on_deleted_account.refresh_from_db()
        assert deposit_on_deleted_account.status == STATEMENT_STATUS.executed
        assert deposit_on_deleted_account.rejection_reason == REJECTION_REASONS.source_account_not_found

        amount_too_high_deposit_statement.refresh_from_db()
        assert amount_too_high_deposit_statement.status == STATEMENT_STATUS.pending_admin
        assert amount_too_high_deposit_statement.rejection_reason == REJECTION_REASONS.unacceptable_amount

        empty_source_iban_deposit_statement.refresh_from_db()
        assert empty_source_iban_deposit_statement.status == STATEMENT_STATUS.pending_admin
        assert empty_source_iban_deposit_statement.rejection_reason == REJECTION_REASONS.empty_source_account

        withdraw_deposit.refresh_from_db()
        assert withdraw_deposit.status == STATEMENT_STATUS.new
        assert withdraw_deposit.rejection_reason is None

        deposit_with_shared_account.refresh_from_db()
        assert deposit_with_shared_account.status == STATEMENT_STATUS.rejected
        assert deposit_with_shared_account.rejection_reason == REJECTION_REASONS.shared_source_account

        # Correct CoBankUserDeposit objects should be created
        assert CoBankUserDeposit.objects.filter(cobank_statement=deposit_on_unconfirmed_account).count() == 1
        assert CoBankUserDeposit.objects.filter(cobank_statement=no_feature_flag_deposit_statement).count() == 1
        assert CoBankUserDeposit.objects.filter(cobank_statement=ineligible_user_deposit_statement).count() == 1
        assert CoBankUserDeposit.objects.filter(cobank_statement=deposit_on_deleted_account).count() == 1
        assert CoBankUserDeposit.objects.filter(cobank_statement=nonexistent_iban_deposit_statement).count() == 0
        assert CoBankUserDeposit.objects.filter(cobank_statement=amount_too_high_deposit_statement).count() == 0
        assert CoBankUserDeposit.objects.filter(cobank_statement=empty_source_iban_deposit_statement).count() == 0
        assert CoBankUserDeposit.objects.filter(cobank_statement=withdraw_deposit).count() == 0
        assert CoBankUserDeposit.objects.filter(cobank_statement=deposit_with_shared_account).count() == 0

    # -----------------------------
    # test_change_statement_status
    # -----------------------------
    def test_change_statement_status_invalid_statement(self):
        """
        Test that the method does nothing if the statement doesn't exist.
        """
        result = self.settler.change_statement_status(statement_pk=-1, changes={'status': STATEMENT_STATUS.rejected})
        assert result is None  # No statement exists, nothing happens, the status of only statement doesn't change
        assert self.deposit_statement.status == STATEMENT_STATUS.new

    def test_change_statement_on_pending_admin_status_missing_status(self):
        """
        Test that the method does nothing if 'status' is not provided in changes, even if source_account is valid
        """
        statement = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            source_account='',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.pending_admin,
        )
        result = self.settler.change_statement_status(statement_pk=statement.pk, changes={'source_account': 'SRC-9875'})
        assert result is None  # No 'status' key in changes.
        statement.refresh_from_db()
        assert statement.status == STATEMENT_STATUS.pending_admin  # Status remains unchanged.

    def test_change_statement_status_invalid_transition(self):
        """
        Test that the method does nothing if the status transition is invalid.
        """
        statement = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            source_account='SRC-9875',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.rejected,
        )
        result = self.settler.change_statement_status(
            statement_pk=statement.pk, changes={'status': STATEMENT_STATUS.executed}
        )
        assert result is None  # Transition rejected -> executed is invalid.
        statement.refresh_from_db()
        assert statement.status == STATEMENT_STATUS.rejected  # Status remains unchanged.

    def test_change_statement_status_simple_transition(self):
        """
        Test a valid status change for a non-pending_admin statement.
        """
        statement = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            source_account='SRC-9875',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.rejected,
            provider_statement_id='12345',
        )
        result = self.settler.change_statement_status(
            statement_pk=statement.pk, changes={'status': STATEMENT_STATUS.refunded}
        )
        assert result is None  # No return value expected.
        statement.refresh_from_db()
        assert statement.status == STATEMENT_STATUS.refunded  # Status changes successfully.

    @patch(
        'django.conf.settings.NOBITEX_OPTIONS',
        {'coBankLimits': {'maxDeposit': 10000, 'minDeposit': 500}, 'coBankFee': {'rate': Decimal('0.0001')}},
    )
    @patch.object(Settler, 'create_deposit')
    def test_change_statement_status_pending_admin_to_executed_without_source_iban(self, mock_create_deposit):
        """
        Test that the method does nothing if transitioning from pending_admin to executed
        without providing source_iban in changes.
        """
        statement = CoBankStatement.objects.create(
            amount=Decimal('5000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            source_iban='',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.pending_admin,
        )
        result = self.settler.change_statement_status(
            statement_pk=statement.pk, changes={'status': STATEMENT_STATUS.executed}
        )
        assert result is None  # No return value expected.

        statement.refresh_from_db()
        assert statement.status == STATEMENT_STATUS.pending_admin  # Status remains unchanged due to empty iban
        # validate_deposits should be called, but statement remains invalid, so create_deposit is not called
        assert mock_create_deposit.call_count == 0  # create_deposit should not be called.

    @patch(
        'django.conf.settings.NOBITEX_OPTIONS',
        {'coBankLimits': {'maxDeposit': 10000, 'minDeposit': 500}, 'coBankFee': {'rate': Decimal('0.0001')}},
    )
    @patch.object(Settler, 'create_deposit')
    def test_update_iban_status_in_changes_but_unchanged(self, mock_create_deposit):
        """
        Test that the method updates the IBAN when the status is in the changes
        but hasn't actually changed, and the IBAN was previously empty.
        """
        statement = CoBankStatement.objects.create(
            amount=Decimal('5000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            source_iban='',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.pending_admin,
        )
        result = self.settler.change_statement_status(
            statement_pk=statement.pk, changes={'status': STATEMENT_STATUS.pending_admin, 'source_iban': '1234'}
        )
        assert result is None

        statement.refresh_from_db()
        assert statement.status == STATEMENT_STATUS.pending_admin
        assert statement.source_iban == '1234'
        assert mock_create_deposit.call_count == 0  # create_deposit should not be called.

    @patch(
        'django.conf.settings.NOBITEX_OPTIONS',
        {'coBankLimits': {'maxDeposit': 100000, 'minDeposit': 500}, 'coBankFee': {'rate': Decimal('0.0001')}},
    )

    @patch(
        'django.conf.settings.NOBITEX_OPTIONS',
        {'coBankLimits': {'maxDeposit': 100000, 'minDeposit': 500}, 'coBankFee': {'rate': Decimal('0.0001')}},
    )
    def test_change_statement_status_pending_admin_to_executed_with_source_iban(self):
        """
        Test transitioning from pending_admin to executed with source_iban of self.user provided.
        """

        statement = CoBankStatement.objects.create(
            amount=Decimal('50000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            source_account='something-wrong',
            source_iban='',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.pending_admin,
        )

        result = self.settler.change_statement_status(
            statement_pk=statement.pk,
            changes={'status': STATEMENT_STATUS.executed, 'source_iban': 'IR500190000000218005998002'},
        )

        assert result is None  # No return value expected.

        statement.refresh_from_db()
        assert statement.status == STATEMENT_STATUS.executed  # Status changes successfully.
        assert statement.source_account == 'something-wrong'  # Source account not changed.
        assert statement.source_iban == 'IR500190000000218005998002'  # Source iban is updated.
        assert Transaction.objects.filter(wallet__user=self.user, wallet__currency=RIAL, amount=Decimal('49995'))
        assert CoBankUserDeposit.objects.filter(user=self.user, amount=Decimal('50000'), fee=Decimal('5'))

    def test_change_statement_status_pending_admin_to_rejected(self):
        """
        Test transitioning from pending_admin to rejected without needing source_account.
        """
        statement = CoBankStatement.objects.create(
            amount=Decimal('5000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            source_account='',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.pending_admin,
            provider_statement_id='12345',
        )
        result = self.settler.change_statement_status(
            statement_pk=statement.pk,
            changes={'status': STATEMENT_STATUS.rejected},
        )
        assert result is None  # No return value expected.

        statement.refresh_from_db()
        assert statement.status == STATEMENT_STATUS.rejected
        assert statement.source_account == ''  # Source account remains unchanged.

    @patch(
        'django.conf.settings.NOBITEX_OPTIONS',
        {'coBankLimits': {'maxDeposit': 100000, 'minDeposit': 500}, 'coBankFee': {'rate': Decimal('0.0001')}},
    )
    def test_change_statement_status_pending_admin_to_executed_on_valid_statement(self):
        """
        Test transitioning from pending_admin to executed without needing source_account.
        This case can happen when user did not have feature flag at the time of making the bank transfer,
        or when their account was not added in Nobitex when making the bank transfer.
        """
        # This statement is now valid but previously, due to lack of feature flag or something else,
        # it went to pending_admin state
        statement = CoBankStatement.objects.create(
            amount=Decimal('5000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            source_iban='IR500190000000218005998002',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.pending_admin,
        )
        result = self.settler.change_statement_status(
            statement_pk=statement.pk, changes={'status': STATEMENT_STATUS.executed}
        )
        assert result is None  # No return value expected.

        statement.refresh_from_db()
        assert statement.status == STATEMENT_STATUS.executed  # Status changes successfully.
        assert statement.source_iban == 'IR500190000000218005998002'  # Source iban remains unchanged.
        assert CoBankUserDeposit.objects.filter(cobank_statement=statement, transaction__isnull=False).exists()

    @patch(
        'django.conf.settings.NOBITEX_OPTIONS',
        {'coBankLimits': {'maxDeposit': 100000, 'minDeposit': 500}, 'coBankFee': {'rate': Decimal('0.0001')}},
    )
    def test_change_statement_status_pending_admin_to_executed_on_statement_above_max_amount(self):
        """
        Test transitioning from pending_admin to executed in case of high amount.
        In this case, when admin wishes to change the status from pending_admin to executed, we bypass
        the high_amount validation that previously caused the statement to go to pending_admin status.
        """
        statement = CoBankStatement.objects.create(
            amount=Decimal('100001'),  # high amount
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            source_iban='IR500190000000218005998002',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.pending_admin,
            rejection_reason=REJECTION_REASONS.unacceptable_amount,
        )
        result = self.settler.change_statement_status(
            statement_pk=statement.pk, changes={'status': STATEMENT_STATUS.executed}
        )
        assert result is None  # No return value expected.

        statement.refresh_from_db()
        assert statement.status == STATEMENT_STATUS.executed  # Status changes successfully.
        assert statement.source_iban == 'IR500190000000218005998002'  # Source iban remains unchanged.
        assert CoBankUserDeposit.objects.filter(cobank_statement=statement, transaction__isnull=False).exists()

    @patch(
        'django.conf.settings.NOBITEX_OPTIONS',
        {'coBankLimits': {'maxDeposit': 100000, 'minDeposit': 500}, 'coBankFee': {'rate': Decimal('0.0001')}},
    )
    def test_change_statement_status_pending_admin_to_executed_on_double_spend_cases(self):
        """
        Test transitioning from pending_admin to executed in case of double spend suspicion.
        In this case, when admin wishes to change the status from pending_admin to executed, we ignore
        the double_spend validation that previously caused the statement to go to pending_admin status.
        """
        old_statement = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            source_iban='IR500190000000218005998002',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.pending_admin,
            rejection_reason=REJECTION_REASONS.old_transaction,
        )
        repeated_reference_code_statement = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            source_iban='IR500190000000218005998002',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.pending_admin,
            rejection_reason=REJECTION_REASONS.repeated_reference_code,
        )
        result = self.settler.change_statement_status(
            statement_pk=old_statement.pk, changes={'status': STATEMENT_STATUS.executed}
        )
        assert result is None  # No return value expected.

        old_statement.refresh_from_db()
        assert old_statement.status == STATEMENT_STATUS.executed  # Status changes successfully.
        assert old_statement.source_iban == 'IR500190000000218005998002'  # Source iban remains unchanged.
        assert CoBankUserDeposit.objects.filter(cobank_statement=old_statement, transaction__isnull=False).exists()

        result = self.settler.change_statement_status(
            statement_pk=repeated_reference_code_statement.pk, changes={'status': STATEMENT_STATUS.executed}
        )
        assert result is None  # No return value expected.

        repeated_reference_code_statement.refresh_from_db()
        assert repeated_reference_code_statement.status == STATEMENT_STATUS.executed  # Status changes successfully.
        assert (
            repeated_reference_code_statement.source_iban == 'IR500190000000218005998002'
        )  # Source iban remains unchanged.
        assert CoBankUserDeposit.objects.filter(
            cobank_statement=repeated_reference_code_statement, transaction__isnull=False
        ).exists()

    def test_update_iban_on_new_status_with_missing_source_iban(self):
        """
        Test that source_iban is updated when statement has 'new' status,
        source_iban is missing, and changes include 'source_iban'.
        """
        statement = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            source_iban='',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.new,
        )

        result = self.settler.change_statement_status(
            statement_pk=statement.pk,
            changes={'source_iban': 'IR500190000000218005998002'},
        )
        assert result is None

        statement.refresh_from_db()
        assert statement.source_iban == 'IR500190000000218005998002'

    def test_change_statement_status_does_not_overwrite_existing_iban(self):
        """
        Test that source_iban is not changed if it already exists on the statement.
        """
        statement = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            source_iban='IR000000000000000000000000',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.new,
        )

        result = self.settler.change_statement_status(
            statement_pk=statement.pk,
            changes={'source_iban': 'IR500190000000218005998002'},
        )
        assert result is None

        statement.refresh_from_db()
        assert statement.source_iban == 'IR000000000000000000000000'  # unchanged

    def test_change_statement_status_update_ban_does_nothing_for_unpermitted_status(self):
        """
        Test that source_iban is not updated if statement status is not 'new' or 'pending_admin'.
        """
        statement = CoBankStatement.objects.create(
            amount=Decimal('500'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            source_iban='',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.rejected,  # not allowed
        )

        result = self.settler.change_statement_status(
            statement_pk=statement.pk,
            changes={'source_iban': 'IR500190000000218005998002'},
        )
        assert result is None

        statement.refresh_from_db()
        assert statement.source_iban == ''  # not updated

    # -----------------------------
    # test_increase_deposit_metrics
    # -----------------------------
    @patch('exchange.corporate_banking.services.settler.metric_incr')
    def test_increase_deposit_metrics(self, mock_metric_incr):
        another_cobank_operational_account = CoBankAccount.objects.create(
            provider_bank_id=4,
            bank=NOBITEX_BANK_CHOICES.saman,
            iban='IR999999999999999999999992',
            account_number='OPER-1235',
            account_tp=ACCOUNT_TP.operational,
        )
        metric_statuses = [
            STATEMENT_STATUS.validated,  # 1 statement from this status will be created
            STATEMENT_STATUS.rejected,  # 2 statements from this status will be created
            STATEMENT_STATUS.pending_admin,  # 3 statements from this status will be created
            STATEMENT_STATUS.executed,  # 4 statements from this status will be created
        ]
        number_of_objects = 0
        statements = []
        for status in metric_statuses:
            number_of_objects += 1
            for i in range(number_of_objects):
                statements.append(
                    CoBankStatement(
                        amount=Decimal('500'),
                        tp=STATEMENT_TYPE.deposit,
                        tracing_number=f'TRX-006{i}',
                        source_account='SRC-9876',
                        destination_account=self.cobank_operational_account,  # Saderat Bank
                        status=status,
                    )
                )
                statements.append(
                    CoBankStatement(
                        amount=Decimal('500'),
                        tp=STATEMENT_TYPE.deposit,
                        tracing_number=f'TRX-0067{i}',
                        source_account='SRC-9876',
                        destination_account=another_cobank_operational_account,  # Saman Bank
                        status=status,
                    )
                )
        self.settler._increase_deposit_metrics(statements)
        assert mock_metric_incr.call_count == 8  # 4 statuses per 2 banks
        assert mock_metric_incr.call_args_list == [
            call('metric_cobanking_core_services_count', amount=1, labels=('deposits', 'Toman', 'saderat', 'valid')),
            call('metric_cobanking_core_services_count', amount=1, labels=('deposits', 'Toman', 'saman', 'valid')),
            call('metric_cobanking_core_services_count', amount=2, labels=('deposits', 'Toman', 'saderat', 'rejected')),
            call('metric_cobanking_core_services_count', amount=2, labels=('deposits', 'Toman', 'saman', 'rejected')),
            call(
                'metric_cobanking_core_services_count',
                amount=3,
                labels=('deposits', 'Toman', 'saderat', 'pendingAdmin'),
            ),
            call(
                'metric_cobanking_core_services_count', amount=3, labels=('deposits', 'Toman', 'saman', 'pendingAdmin')
            ),
            call('metric_cobanking_core_services_count', amount=4, labels=('deposits', 'Toman', 'saderat', 'executed')),
            call('metric_cobanking_core_services_count', amount=4, labels=('deposits', 'Toman', 'saman', 'executed')),
        ]

    def test_lag_metric(self):
        deposits = []

        # Saderat 2 hours delay
        for i in range(5):
            deposits.append(
                CoBankUserDeposit(
                    cobank_statement=CoBankStatement(
                        amount=Decimal('500'),
                        tp=STATEMENT_TYPE.deposit,
                        tracing_number='TRX-006',
                        source_account='SRC-9875',
                        destination_account=self.cobank_operational_account,
                        status=STATEMENT_STATUS.new,
                        transaction_datetime=ir_now() - timedelta(hours=i),
                    ),
                    user_id=self.user.id,
                    user_bank_account_id=1,
                    amount=1000,
                    created_at=ir_now(),
                )
            )

        # Statement without transaction_datetime and should be excluded
        deposits.append(
            CoBankUserDeposit(
                cobank_statement=CoBankStatement(
                    amount=Decimal('500'),
                    tp=STATEMENT_TYPE.deposit,
                    tracing_number='TRX-006',
                    source_account='SRC-9875',
                    destination_account=self.cobank_operational_account,
                    status=STATEMENT_STATUS.new,
                ),
                user_id=self.user.id,
                user_bank_account_id=1,
                amount=1000,
                created_at=ir_now(),
            )
        )

        # Saman 40 hours delay
        deposits.append(
            CoBankUserDeposit(
                cobank_statement=CoBankStatement(
                    amount=Decimal('500'),
                    tp=STATEMENT_TYPE.deposit,
                    tracing_number='TRX-006',
                    source_account='SRC-9875',
                    destination_account=CoBankAccount(
                        provider_bank_id=4,
                        bank=NOBITEX_BANK_CHOICES.saman,
                        iban='IR999999999999999999999992',
                        account_number='OPER-1234',
                        account_tp=ACCOUNT_TP.operational,
                    ),
                    status=STATEMENT_STATUS.new,
                    transaction_datetime=ir_now() - timedelta(hours=40),
                ),
                user_id=self.user.id,
                user_bank_account_id=1,
                amount=1000,
                created_at=ir_now(),
            )
        )

        Settler()._log_deposit_lag_metric(deposits)

        assert cache.get('time_cobank_deposit_settlement_lag__saman_avg') == 40 * 60 * 60
        assert cache.get('time_cobank_deposit_settlement_lag__saderat_avg') == 2 * 60 * 60

    @patch(
        'django.conf.settings.NOBITEX_OPTIONS',
        {'coBankLimits': {'maxDeposit': 10000, 'minDeposit': 500}, 'coBankFee': {'rate': Decimal('0.0001')}},
    )
    def test_settle_pending_statements(self):
        # Pending statement with missing source account expected to be settled.
        pending_deposit_created_now = CoBankStatement.objects.create(
            amount=Decimal('5000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-001',
            source_iban='IR500190000000218005998002',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.pending_admin,
            rejection_reason=REJECTION_REASONS.source_account_not_found,
            created_at=ir_now(),
        )

        # Pending statement with empty source account reason expected to be settled.
        old_pending_deposit_empty_source = CoBankStatement.objects.create(
            amount=Decimal('4000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-002',
            source_iban='IR500190000000218005998002',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.pending_admin,
            rejection_reason=REJECTION_REASONS.source_account_not_found,
            created_at=ir_now() - timedelta(days=365),  # Creation time shouldn't have effect on settlement.
        )
        # Expected to be settled as it's rejected previously and rejection reason was ineligible_user.
        rejected_deposit_ineligible_user = CoBankStatement.objects.create(
            amount=Decimal('2000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-003',
            source_iban='IR500190000000218005998002',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.rejected,
            rejection_reason=REJECTION_REASONS.ineligible_user,
            created_at=ir_now() - timedelta(days=365),
        )

        # Expected not be settled as it's rejected previously and rejection reason was not ineligible_user.
        rejected_deposit_repeated_refcode = CoBankStatement.objects.create(
            amount=Decimal('2000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-004',
            source_iban='IR500190000000218005998002',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.rejected,
            rejection_reason=REJECTION_REASONS.repeated_reference_code,
            created_at=ir_now() - timedelta(days=365),
        )

        # Mustn't be settled as it's not pending.
        new_deposit = CoBankStatement.objects.create(
            amount=Decimal('3000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-005',
            source_iban='IR500190000000218005998002',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.new,
            rejection_reason=REJECTION_REASONS.empty_source_account,
            created_at=ir_now() - timedelta(days=365),
        )

        Settler(settling_pending_deposits=True).settle_statements()

        # These statements expected to be settled.
        for statement in [
            pending_deposit_created_now,
            old_pending_deposit_empty_source,
            rejected_deposit_ineligible_user,
        ]:
            statement.refresh_from_db()
            assert (
                statement.status == STATEMENT_STATUS.executed
            ), f'Statement {statement.tracing_number} status must be executed.'
            # Check that user deposit is created.
            assert CoBankUserDeposit.objects.filter(cobank_statement=statement).exists()

        # These statements expected to not be settled.
        for statement in [new_deposit, rejected_deposit_repeated_refcode]:
            statement.refresh_from_db()
            assert (
                statement.status != STATEMENT_STATUS.executed
            ), f'Statement {statement.tracing_number} status must not be executed.'
            # Check that user deposit is not created.
            assert not CoBankUserDeposit.objects.filter(cobank_statement=statement).exists()
