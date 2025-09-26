import random
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import BankAccount, User
from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from exchange.corporate_banking.exceptions import (
    AmountValidationException,
    BankAccountValidationException,
    FeatureFlagValidationException,
    PossibleDoubleSpendException,
    RefundValidationException,
    UserLevelValidationException,
)
from exchange.corporate_banking.models import (
    ACCOUNT_TP,
    COBANK_PROVIDER,
    NOBITEX_BANK_CHOICES,
    STATEMENT_STATUS,
    STATEMENT_TYPE,
    CoBankAccount,
    CoBankStatement,
)
from exchange.corporate_banking.services.validators import (
    BankAccountValidator,
    DepositAmountValidator,
    DoubleSpendPreventer,
    FeatureFlagValidator,
    RefundStatementValidator,
    UserLevelValidator,
)
from exchange.features.models import QueueItem


class TestValidators(TestCase):
    def setUp(self):
        cache.clear()

        self.user = User.objects.create(
            username=f'alice_{random.randint(0, 1000000)}',
            user_type=User.USER_TYPE_LEVEL1,
        )
        self.bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='123456',
            shaba_number='IR999999999999999999999991',
            owner_name=self.user.username,
            bank_name='something',
            bank_id=BankAccount.BANK_ID.saman,
            confirmed=True,
        )
        self.cobank_account = CoBankAccount.objects.create(
            provider_bank_id=4,
            bank=NOBITEX_BANK_CHOICES.saderat,
            iban='IR999999999999999999999992',
            account_number='111222333',
            account_tp=ACCOUNT_TP.operational,
        )
        self.jibit_cobank_account = CoBankAccount.objects.create(
            provider_bank_id=4,
            bank=NOBITEX_BANK_CHOICES.saderat,
            iban='IR999999999999999999999993',
            account_number='222333444',
            account_tp=ACCOUNT_TP.operational,
            provider=COBANK_PROVIDER.jibit,
        )
        self.statement = CoBankStatement.objects.create(
            amount=Decimal('100000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-001',
            source_account='123456',
            source_iban='IR999999999999999999999991',
            source_card='',
            destination_account=self.cobank_account,
            provider_statement_id='PROV-001',
            api_response={'ref1': 'ABC123', 'ref2': 'XYZ789', 'bankTransactionId': 'BNK001'},
        )
        self.statement2 = CoBankStatement.objects.create(
            amount=Decimal('200000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-002',
            source_account='999999',
            source_iban='',
            source_card='',
            destination_account=self.cobank_account,
            provider_statement_id='PROV-002',
            api_response={'ref1': 'ABC111', 'ref2': 'XYZ222', 'bankTransactionId': 'BNK001'},
        )
        self.flag_item = QueueItem.objects.create(
            user=self.user,
            feature=QueueItem.FEATURES.cobank,
            status=QueueItem.STATUS.done,
        )

    # -----------------------
    # FeatureFlagValidator
    # -----------------------

    def test_feature_flag_validator_success(self):
        validator = FeatureFlagValidator()
        assert validator.validate(self.user) == self.user  # returns the user if feature is available

    def test_feature_flag_validator_no_user_item(self):
        """
        If the user doesn't have a done QueueItem with feature=cobank,
        it should raise FeatureFlagValidationException('FeatureUnavailable').
        """
        self.flag_item.delete()  # Remove the user's feature
        validator = FeatureFlagValidator()
        with pytest.raises(FeatureFlagValidationException, match='FeatureUnavailable'):
            validator.validate(self.user)

    def test_feature_flag_validator_no_user_item_but_check_flag_is_disabled(self):
        self.flag_item.delete()  # Remove the user's feature
        Settings.set('cobank_check_feature_flag', 'no')

        validator = FeatureFlagValidator()
        assert validator.validate(self.user) == self.user

    def test_feature_flag_validator_unknown_user(self):
        """
        If we pass something that can't resolve to a user,
        it should raise FeatureFlagValidationException('UserNotFound').
        """
        validator = FeatureFlagValidator()
        try:
            validator.validate('nonexistent-user-string')
            assert False, 'Expected FeatureFlagValidationException but none raised.'
        except FeatureFlagValidationException as e:
            assert e.code == 'UserNotFound'

    def test_feature_flag_validator_with_valid_username(self):
        """
        If we pass something that can't resolve to a user,
        it should raise FeatureFlagValidationException('UserNotFound').
        """
        validator = FeatureFlagValidator()
        assert validator.validate(self.user.username) == self.user

    # -----------------------
    # UserLevelValidator
    # -----------------------

    def test_user_level_validator_success(self):
        validator = UserLevelValidator()
        assert validator.validate(self.user) == self.user
        assert validator.validate(self.user.username) == self.user

    def test_user_level_validator_ineligible_user(self):
        """
        If user.user_type < USER_TYPE_LEVEL1, raise IneligibleUser.
        """
        self.user.user_type = 0  # below LEVEL1
        self.user.save()
        validator = UserLevelValidator()
        try:
            validator.validate(self.user)
            assert False, 'Expected UserLevelValidationException but none raised.'
        except UserLevelValidationException as e:
            assert e.code == 'IneligibleUser'

    def test_user_level_validator_user_not_found(self):
        """
        If there's no user object, or invalid type => UserNotFound.
        """
        validator = UserLevelValidator()
        try:
            validator.validate(None)
            assert False, 'Expected UserLevelValidationException but none raised.'
        except UserLevelValidationException as e:
            assert e.code == 'UserNotFound'

    def test_user_validator_on_object_having_user(self):
        validator = UserLevelValidator()
        assert validator.validate(self.bank_account) == self.user

    # -----------------------
    # BankAccountValidator
    # -----------------------

    def test_bank_account_validator_success(self):
        validator = BankAccountValidator()
        assert validator.validate(self.bank_account) == self.bank_account

    def test_bank_account_validator_co_bank_statement(self):
        """
        If passed a CoBankStatement, the validator uses statement.source_iban to find the BankAccount.
        """
        validator = BankAccountValidator()
        # statement.source_iban='IR999999999999999999999991', matches self.iban
        assert validator.validate(self.statement) == self.bank_account

    def test_bank_account_validator_empty(self):
        validator = BankAccountValidator()
        try:
            validator.validate('')
            assert False, 'Expected BankAccountValidationException but none raised.'
        except BankAccountValidationException as e:
            assert e.code == 'EmptyIban'

    def test_bank_account_validator_not_found(self):
        """
        If there's no matching bank account, raise 'BankAccountNotFound'.
        """
        self.bank_account.delete()
        validator = BankAccountValidator()
        try:
            validator.validate('123456')  # Not in DB
            assert False, 'Expected BankAccountValidationException but none raised.'
        except BankAccountValidationException as e:
            assert e.code == 'BankAccountNotFound'

    def test_bank_account_validator_invalid_unconfirmed_account(self):
        """
        If more than one account has the same account_number => 'SharedBankAccount'.
        """
        # Create a second BankAccount with the same account_number
        BankAccount.objects.create(user=self.user, account_number='345678', confirmed=False)
        validator = BankAccountValidator()
        try:
            validator.validate('345678')
            assert False, 'Expected BankAccountValidationException but none raised.'
        except BankAccountValidationException as e:
            assert e.code == 'BankAccountNotFound'

    def test_bank_account_validator_shared_account(self):
        """
        If more than one account has the same account_number => 'SharedBankAccount'.
        """
        # Create a second BankAccount with the same account_number but belonging to another user
        second_user = User.objects.create(username=f'bob_{random.randint(0, 1000000)}')
        BankAccount.objects.create(user=second_user, shaba_number=self.bank_account.shaba_number, confirmed=True)
        validator = BankAccountValidator()
        try:
            validator.validate('IR999999999999999999999991')
            assert False, 'Expected BankAccountValidationException but none raised.'
        except BankAccountValidationException as e:
            assert e.code == 'SharedBankAccount'

    def test_bank_account_validator_empty_sources_in_cobank_statement_obj(self):
        validator = BankAccountValidator()
        statement = CoBankStatement.objects.create(
            amount=Decimal('100000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-001',
            source_account=None,
            source_iban=None,
            destination_account=self.cobank_account,
        )
        try:
            validator.validate(statement)
            assert False, 'Expected BankAccountValidationException but none raised.'
        except BankAccountValidationException as e:
            assert e.code == 'EmptyIban'

    def test_bank_account_validator_find_iban_in_cobank_statement_obj(self):
        account = BankAccount.objects.create(user=self.user, shaba_number='IR12032541268751425415', confirmed=True)
        validator = BankAccountValidator()
        statement = CoBankStatement.objects.create(
            amount=Decimal('100000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-001',
            source_account=None,
            source_iban='IR12032541268751425415',
            destination_account=self.cobank_account,
        )
        assert validator.validate(statement) == account

    def test_bank_account_validator_one_user_multiple_accounts(self):
        """
        If more than one account has the same account_number => 'SharedBankAccount'.
        """
        # Create a second BankAccount with the same iban and user but deleted
        BankAccount.objects.create(
            user=self.user,
            shaba_number=self.bank_account.shaba_number,
            confirmed=True,
            is_deleted=True,
        )
        validator = BankAccountValidator()
        result = validator.validate(self.bank_account.shaba_number)
        assert result == self.bank_account

    # -----------------------
    # DepositAmountValidator
    # -----------------------

    @patch('django.conf.settings.NOBITEX_OPTIONS', {'coBankLimits': {'maxDeposit': 2000, 'minDeposit': 500}})
    def test_deposit_amount_validator_success(self):
        """
        The snippet code says if amount < min => too low, if amount > min => too high,
        so the valid scenario is amount == min.
        """
        validator = DepositAmountValidator()
        obj = Decimal('500')
        result = validator.validate(obj)
        assert result == obj

    @patch('django.conf.settings.NOBITEX_OPTIONS', {'coBankLimits': {'maxDeposit': 2000, 'minDeposit': 500}})
    def test_deposit_amount_validator_too_low(self):
        validator = DepositAmountValidator()
        try:
            validator.validate(Decimal('499'))
            assert False, "Expected AmountValidationException('AmountTooLow') but none raised."
        except AmountValidationException as e:
            assert e.code == 'AmountTooLow'

    @patch('django.conf.settings.NOBITEX_OPTIONS', {'coBankLimits': {'maxDeposit': 2000, 'minDeposit': 500}})
    def test_deposit_amount_validator_too_high(self):
        validator = DepositAmountValidator()
        try:
            validator.validate(Decimal('2001'))
            assert False, "Expected AmountValidationException('AmountTooHigh') but none raised."
        except AmountValidationException as e:
            assert e.code == 'AmountTooHigh'

    def test_deposit_amount_validator_invalid_amount(self):
        validator = DepositAmountValidator()
        try:
            validator.validate(None)
            assert False, "Expected AmountValidationException('InvalidAmount') but none raised."
        except AmountValidationException as e:
            assert e.code == 'InvalidAmount'

    # ---------------------
    # DoubleSpendPreventer
    # ---------------------

    @patch('exchange.corporate_banking.services.validators.logstash_logger.info')
    def test_double_spend_preventer_no_conflict(self, logger_mock: MagicMock):
        """
        Ensures that if there is no conflicting statement (same source fields, same references,
        same destination/amount), the validator does not raise an exception.
        """
        validator = DoubleSpendPreventer()

        # self.statement has no existing duplicate → should pass
        validated_obj = validator.validate(self.statement)
        assert validated_obj == self.statement
        logger_mock.assert_not_called()

        # self.statement2 also has no conflict with self.statement → should pass
        validated_obj_2 = validator.validate(self.statement2)
        assert validated_obj_2 == self.statement2
        logger_mock.assert_not_called()

        # self.statement2 also has no api_response and no conflicting tracing_number → should pass
        self.statement2.api_response = dict()
        self.statement2.save()
        validated_obj_2 = validator.validate(self.statement2)
        assert validated_obj_2 == self.statement2
        logger_mock.assert_not_called()

        # self.statement2 has api_response but self.statement doesn't → should pass
        self.statement2.api_response = self.statement.api_response.copy()
        self.statement2.save()
        self.statement.api_response = dict()
        self.statement.save()
        validated_obj_2 = validator.validate(self.statement2)
        assert validated_obj_2 == self.statement2
        logger_mock.assert_not_called()

    @patch('exchange.corporate_banking.services.validators.logstash_logger.info')
    def test_double_spend_preventer_no_conflict_with_same_references_without_similar_source_destination_amount(
        self,
        logger_mock,
    ):
        """
        No conflict should be raised when tracing_number and all api_response reference fields are the same but:
          - destination_account is different, or
          - source account (account/iban/card) is different, or
          - amount is different
        """
        validator = DoubleSpendPreventer()

        # 1) Make self.statement2 have the same references as self.statement
        self.statement2.tracing_number = self.statement.tracing_number
        self.statement2.api_response = self.statement.api_response.copy()

        # 2) similar source and destination but different amounts
        self.statement.source_card = self.statement2.source_card = '1234567890123456'
        self.statement.destination_account = self.statement2.destination_account = self.jibit_cobank_account
        self.statement.save()
        self.statement2.save()

        validated_obj2 = validator.validate(self.statement2)
        assert validated_obj2 == self.statement2
        logger_mock.assert_not_called()

        # 3) similar source and amount but different destinations
        self.statement.source_card = self.statement2.source_card = '1234567890123456'
        self.statement2.amount = self.statement.amount
        self.statement.destination_account = self.cobank_account
        self.statement2.destination_account = self.jibit_cobank_account
        self.statement.save()
        self.statement2.save()

        validated_obj2 = validator.validate(self.statement2)
        assert validated_obj2 == self.statement2
        logger_mock.assert_not_called()

        # 4) similar amount and destination but different sources
        self.statement.source_card = '1234567890123456'
        self.statement2.source_card = '0987654321098765'
        self.statement2.amount = self.statement.amount
        self.statement.destination_account = self.statement2.destination_account = self.cobank_account
        self.statement.save()
        self.statement2.save()

        validated_obj2 = validator.validate(self.statement2)
        assert validated_obj2 == self.statement2
        logger_mock.assert_not_called()

        # 5) similar amount and destination but different sources -- case of different origins
        self.statement.source_card = ''
        self.statement2.source_card = '0987654321098765'
        self.statement.source_iban = 'IR999999999999999999999994'
        self.statement2.source_iban = ''
        self.statement2.amount = self.statement.amount
        self.statement.destination_account = self.statement2.destination_account = self.cobank_account
        self.statement.save()
        self.statement2.save()

        validated_obj2 = validator.validate(self.statement2)
        assert validated_obj2 == self.statement2
        logger_mock.assert_not_called()

    @patch('exchange.corporate_banking.services.validators.logstash_logger.info')
    def test_double_spend_preventer_conflict_when_statements_with_same_provider_have_same_tracing_number(
        self,
        logger_mock: MagicMock,
    ):
        """
        Creates a conflicting statement that shares:
          - same destination_account & amount
          - same source_iban
          - same tracing number
        Expects PossibleDoubleSpendException to be raised.
        """
        validator = DoubleSpendPreventer()

        # Make self.statement2 conflict with self.statement:
        # 1) same amount and destination as self.statement
        self.statement2.amount = self.statement.amount
        self.statement2.destination_account = self.statement.destination_account

        # 2) same source_account so it triggers the same-source query condition
        self.statement2.source_account = self.statement.source_account

        # 3) same references for same-provider scenario
        self.statement2.tracing_number = self.statement.tracing_number

        # 4) ignore ref1, ref2 and bankTransactionId
        self.statement2.api_response['ref1'] = None
        self.statement2.api_response['ref2'] = None
        self.statement2.api_response['bankTransactionId'] = None
        self.statement2.save()

        with pytest.raises(PossibleDoubleSpendException, match='RepeatedReferenceCode'):
            validator.validate(self.statement2)

        logger_mock.assert_called_once()

    @patch('exchange.corporate_banking.services.validators.logstash_logger.info')
    def test_double_spend_preventer_conflict_when_statements_with_same_provider_have_same_ref_numbers(
        self,
        logger_mock: MagicMock,
    ):
        """
        Creates a conflicting statement that shares:
          - same destination_account & amount
          - same source_iban
          - same tracing_number
          - same references (api_response.ref1, api_response.ref2, or api_response.bankTransactionId)
        Expects PossibleDoubleSpendException to be raised.
        """
        validator = DoubleSpendPreventer()

        # Make self.statement2 conflict with self.statement:
        # 1) same amount and destination as self.statement
        self.statement2.tracing_number = self.statement.tracing_number
        self.statement2.amount = self.statement.amount
        self.statement2.destination_account = self.statement.destination_account

        # 2) same source_iban so it triggers the same-source query condition
        self.statement.source_iban = self.statement2.source_iban = 'IR999999999999999999999994'
        self.statement.save()

        # 3) same references for same-provider scenario: similar ref2 case
        self.statement2.api_response['ref1'] = self.statement.api_response['ref1']
        self.statement2.api_response['ref2'] = self.statement.api_response['ref2']
        self.statement2.api_response['bankTransactionId'] = None

        self.statement2.save()

        with pytest.raises(PossibleDoubleSpendException, match='RepeatedReferenceCode'):
            validator.validate(self.statement2)
        logger_mock.assert_called_once()

        # 4) same references for same-provider scenario: similar bankTransactionId case
        self.statement2.api_response['ref1'] = None
        self.statement2.api_response['ref2'] = None
        self.statement2.api_response['bankTransactionId'] = self.statement.api_response['bankTransactionId']
        self.statement2.save()

        logger_mock.reset_mock()
        with pytest.raises(PossibleDoubleSpendException, match='RepeatedReferenceCode'):
            validator.validate(self.statement2)
        logger_mock.assert_called_once()

    @patch('exchange.corporate_banking.services.validators.logstash_logger.info')
    def test_double_spend_preventer_conflict_with_different_account_providers(self, logger_mock):
        """
        Creates a conflicting statement that shares:
          - same amount and same destination_account but from a different provider
          - same source_iban
          - same references (api_response.ref1 from Toman and api_response.bankTransactionId from Jibit,
          or similar tracing_number s)
        Expects PossibleDoubleSpendException to be raised.
        """
        validator = DoubleSpendPreventer()

        # 1) Make self.statement2 have the same amount and source and destination_iban as self.statement
        self.cobank_account.iban = self.jibit_cobank_account.iban = 'IR999999999999999999999995'
        self.cobank_account.save()
        self.jibit_cobank_account.save()

        self.statement.destination_account = self.cobank_account
        self.statement2.destination_account = self.jibit_cobank_account
        self.statement2.amount = self.statement.amount
        self.statement2.source_iban = self.statement.source_iban

        # 2) similar tracing_number s
        self.statement.tracing_number = self.statement2.tracing_number = 'TRX-1234'

        # 3) ignore ref1, ref2 and bankTransactionId
        self.statement2.api_response['ref1'] = None
        self.statement2.api_response['ref2'] = None
        self.statement2.api_response['bankTransactionId'] = None

        self.statement.save()
        self.statement2.save()

        with pytest.raises(PossibleDoubleSpendException, match='RepeatedReferenceCode'):
            validator.validate(self.statement2)
        logger_mock.assert_called_once()

        # 4) similar Toman's ref1 and Jibit's bankTransactionId
        self.statement2.tracing_number = None
        self.statement2.api_response['ref2'] = None
        self.statement2.api_response['bankTransactionId'] = self.statement.api_response['ref1'] = 'TRX-5678'
        self.statement.save()
        self.statement2.save()

        logger_mock.reset_mock()
        with pytest.raises(PossibleDoubleSpendException, match='RepeatedReferenceCode'):
            validator.validate(self.statement2)
        logger_mock.assert_called_once()

    @patch('exchange.corporate_banking.services.validators.logstash_logger.info')
    def test_double_spend_preventer_conflict_for_old_statements(self, logger_mock):
        """
        Expects PossibleDoubleSpendException to be raised with old deposits
        """
        validator = DoubleSpendPreventer()
        self.statement.transaction_datetime = ir_now() - timedelta(hours=47, minutes=59)
        self.statement.save()
        assert validator.validate(self.statement) == self.statement

        self.statement.transaction_datetime = ir_now() - timedelta(hours=48, seconds=1)
        self.statement.save()
        with pytest.raises(PossibleDoubleSpendException, match='OldTransaction'):
            validator.validate(self.statement)
        logger_mock.assert_not_called()

    # -------------------------
    # Combination of Validators
    # -------------------------

    def test_compound_validators_user_level_and_feature_flag_validators(self):
        validator = UserLevelValidator(FeatureFlagValidator())
        assert validator.validate(self.user) == self.user
        assert validator.validate(self.user.username) == self.user
        assert validator.validate(self.bank_account) == self.user

        try:
            validator.validate('nonexistent-user-string')
            assert False, 'Expected FeatureFlagValidationException but none raised.'
        except FeatureFlagValidationException as e:
            assert e.code == 'UserNotFound'

    def test_compound_validators_user_level_and_bank_account_validators(self):
        validator = UserLevelValidator(FeatureFlagValidator(BankAccountValidator()))
        assert validator.validate(self.bank_account) == self.user
        assert validator.validate(self.bank_account.shaba_number) == self.user
        assert validator.validate(self.statement) == self.user

        try:
            validator.validate('nonexistent-account')
            assert False, 'Expected BankAccountValidationException but none raised.'
        except BankAccountValidationException as e:
            assert e.code == 'BankAccountNotFound'

        try:
            validator.validate('')
            assert False, 'Expected BankAccountValidationException but none raised.'
        except BankAccountValidationException as e:
            assert e.code == 'EmptyIban'

    @patch('django.conf.settings.NOBITEX_OPTIONS', {'coBankLimits': {'maxDeposit': 2000, 'minDeposit': 500}})
    def test_compound_validators_all_validators(self):
        validator = UserLevelValidator(FeatureFlagValidator(BankAccountValidator(DepositAmountValidator())))
        self.statement.amount = Decimal(2000)
        self.statement.save()
        assert validator.validate(self.statement) == self.user

        try:
            self.statement.amount = Decimal(499)
            self.statement.save()
            validator.validate(self.statement)
            assert False, "Expected AmountValidationException('AmountTooLow') but none raised."
        except AmountValidationException as e:
            assert e.code == 'AmountTooLow'

        try:
            self.statement.amount = Decimal(2001)
            self.statement.save()
            validator.validate(self.statement)
            assert False, "Expected AmountValidationException('AmountTooHigh') but none raised."
        except AmountValidationException as e:
            assert e.code == 'AmountTooHigh'


class RefundStatementValidatorTestCase(TestCase):
    def setUp(self):
        self.cobank_operational_account = CoBankAccount.objects.create(
            provider_bank_id=4,
            bank=NOBITEX_BANK_CHOICES.saderat,
            iban='IR999999999999999999999992',
            account_number='OPER-1234',
            account_tp=ACCOUNT_TP.operational,
        )
        self.cobank_operational_account_without_iban = CoBankAccount.objects.create(
            provider_bank_id=4,
            bank=NOBITEX_BANK_CHOICES.saderat,
            iban='',
            account_number='OPER-1234',
            account_tp=ACCOUNT_TP.operational,
        )

        self.valid_statement = CoBankStatement.objects.create(
            amount=Decimal('100.00'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.rejected,
            provider_statement_id='12345',
        )

        self.invalid_type_statement = CoBankStatement.objects.create(
            amount=Decimal('-100.00'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.rejected,
        )

        self.without_iban_statement = CoBankStatement.objects.create(
            amount=Decimal('100.00'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            status=STATEMENT_STATUS.rejected,
            provider_statement_id='12345',
            destination_account=self.cobank_operational_account_without_iban,
        )

        self.without_provider_statement_id = CoBankStatement.objects.create(
            amount=Decimal('100.00'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-006',
            status=STATEMENT_STATUS.rejected,
            provider_statement_id='',
            destination_account=self.cobank_operational_account,
        )

        self.invalid_status_statement = CoBankStatement.objects.create(
            amount=Decimal('50.00'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRX-007',
            destination_account=self.cobank_operational_account,
            status=STATEMENT_STATUS.executed,
        )

    def test_validate_success(self):
        validator = RefundStatementValidator()
        result = validator.validate(self.valid_statement)

        assert result == self.valid_statement

    def test_validate_none_object(self):
        validator = RefundStatementValidator()
        with self.assertRaises(RefundValidationException) as cm:
            validator.validate(None)

        assert str(cm.exception) == 'ObjectIsNotValid'

    def test_validate_invalid_object_type(self):
        validator = RefundStatementValidator()
        invalid_obj = 'not a statement'

        with self.assertRaises(RefundValidationException) as cm:
            validator.validate(invalid_obj)

        assert str(cm.exception) == 'ObjectIsNotValid'

    def test_validate_invalid_status(self):
        validator = RefundStatementValidator()
        with self.assertRaises(RefundValidationException) as cm:
            validator.validate(self.invalid_status_statement)

        assert str(cm.exception) == 'ObjectStatusNotValidToRefund'

    def test_validate_invalid_type(self):
        validator = RefundStatementValidator()
        with self.assertRaises(RefundValidationException) as cm:
            validator.validate(self.invalid_type_statement)

        assert str(cm.exception) == 'StatementIsNotDeposit'

    def test_validate_without_iban(self):
        validator = RefundStatementValidator()
        with self.assertRaises(RefundValidationException) as cm:
            validator.validate(self.without_iban_statement)

        assert str(cm.exception) == 'StatementDestinationAccountWithoutIBAN'

    def test_validate_witout_provider_statement_id(self):
        validator = RefundStatementValidator()
        with self.assertRaises(RefundValidationException) as cm:
            validator.validate(self.without_provider_statement_id)

        assert str(cm.exception) == 'StatementWithoutProviderStatementID'
