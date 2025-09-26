from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db.models import Q, QuerySet

from exchange.accounts.models import BankAccount, User
from exchange.base.calendar import ir_now
from exchange.base.logstash_logging.loggers import logstash_logger
from exchange.base.models import Settings
from exchange.corporate_banking.exceptions import (
    AmountValidationException,
    BankAccountValidationException,
    FeatureFlagValidationException,
    PossibleDoubleSpendException,
    RefundValidationException,
    UserLevelValidationException,
)
from exchange.corporate_banking.models import STATEMENT_STATUS, CoBankStatement
from exchange.features.models import QueueItem


class Validator:
    error: Exception

    def __init__(self, inner_validator: Optional['Validator'] = None):
        self.inner_validator = inner_validator

    def validate(self, obj):
        validated_obj = self.inner_validator.validate(obj) if self.inner_validator else obj
        return self._validate(validated_obj)

    def _validate(self, obj):
        raise NotImplementedError


class FeatureFlagValidator(Validator):
    error = FeatureFlagValidationException

    def _validate(self, obj):
        if Settings.get_value('cobank_check_feature_flag', 'yes') == 'no':
            return obj

        try:
            user = (
                obj if isinstance(obj, User) else (User.objects.get(username=obj) if isinstance(obj, str) else obj.user)
            )
            if not user:
                raise Exception
        except Exception:
            raise self.error('UserNotFound')
        if not QueueItem.objects.filter(user=user, feature=QueueItem.FEATURES.cobank, status=QueueItem.STATUS.done):
            raise self.error('FeatureUnavailable')
        return user


class UserLevelValidator(Validator):
    error = UserLevelValidationException

    def _validate(self, obj):
        try:
            user = (
                obj if isinstance(obj, User) else (User.objects.get(username=obj) if isinstance(obj, str) else obj.user)
            )
            if not user:
                raise Exception
        except Exception:
            raise self.error('UserNotFound')
        if user.user_type < User.USER_TYPE_LEVEL1:
            raise self.error('IneligibleUser')
        return user


class BankAccountValidator(Validator):
    error = BankAccountValidationException

    def _validate(self, obj):
        if not obj:
            raise self.error('EmptyIban')
        if isinstance(obj, CoBankStatement):
            if obj.source_iban:
                obj = obj.source_iban
            else:
                raise self.error('EmptyIban')

        account = BankAccount.objects.filter(shaba_number=obj, confirmed=True) if isinstance(obj, str) else obj
        if not account or (not isinstance(account, BankAccount) and not isinstance(account, QuerySet)):
            raise self.error('BankAccountNotFound')
        if isinstance(account, QuerySet) and len(account) > 1 and len(account.values('user').distinct()) > 1:
            raise self.error('SharedBankAccount')
        if isinstance(account, QuerySet) and len(account) > 1:
            return account.filter(is_deleted=False).first() or account.first()
        return account.first() if isinstance(account, QuerySet) else account


class DepositAmountValidator(Validator):
    error = AmountValidationException

    def __init__(self, inner_validator: Optional['Validator'] = None, bypass_high_amount: bool = False):
        super().__init__(inner_validator)
        self.bypass_high_amount = bypass_high_amount

    def _validate(self, obj):
        if not obj:
            raise self.error('InvalidAmount')
        try:
            amount = (
                Decimal(obj)
                if isinstance(obj, Decimal) or isinstance(obj, float) or isinstance(obj, int)
                else obj.amount
            )
        except Exception:
            raise self.error('InvalidAmount')
        if amount < settings.NOBITEX_OPTIONS['coBankLimits']['minDeposit']:
            raise self.error('AmountTooLow')
        if not self.bypass_high_amount and amount > settings.NOBITEX_OPTIONS['coBankLimits']['maxDeposit']:
            raise self.error('AmountTooHigh')
        return obj


class DoubleSpendPreventer(Validator):
    """
    Trying to prevent possible cases of double spend by two cases:
    - transactions with repeated reference codes:
        - If two transactions have the same source account and the same destination account and the same amount:
            - If they are from Toman provider: similar tracing_number, api_response.ref1, or api_response.ref2 can mean
            a possible double spend case.
            - If they are from Jibit provider: similar tracing_number or api_response.bankTransactionId can mean
            a possible double spend case.
            - If one is from Toman provider and another from Jibit provider (just in case a cobank_account is
            managed by both our providers): similar tracing_number, or similar Toman api_response.ref1 and
            Jibit api_response.bankTransactionId can mean a possible double spend case.
    - old transactions:
        - The latest we might gather a deposit and settle it is at 4 A.M of the next morning the deposit happened
        (see GetDailyStatementsCron). Considering the possibility of retrying to fetch old transactions by admin, we
        consider any deposit beyond 48 hours to be old and a possible double-spend case.
    """

    error = PossibleDoubleSpendException

    def _validate(self, obj):
        if not obj or not isinstance(obj, CoBankStatement):
            return obj

        similar_statements = self._find_statements_with_similar_references(obj)
        if len(similar_statements) > 0:
            logstash_logger.info(
                'Similar statements to StatementId#%s',
                obj.id,
                extra={
                    'params': [statement.id for statement in similar_statements],
                    'index_name': 'cobank_verification',
                },
            )
            raise self.error('RepeatedReferenceCode')

        if obj.transaction_datetime is not None and obj.transaction_datetime < ir_now() - timedelta(hours=48):
            raise self.error('OldTransaction')

        return obj

    def _find_statements_with_similar_references(self, statement: CoBankStatement):
        same_source_query_conditions = (
            (Q(source_iban__isnull=False, source_iban=statement.source_iban) & ~Q(source_iban__exact=''))
            | (Q(source_account__isnull=False, source_account=statement.source_account) & ~Q(source_account__exact=''))
            | (Q(source_card__isnull=False, source_card=statement.source_card) & ~Q(source_card__exact=''))
        )
        same_reference_numbers_within_the_same_provider_query_conditions = Q(
            destination_account__provider=statement.destination_account.provider,
        )

        if statement.tracing_number:
            same_reference_numbers_within_the_same_provider_query_conditions &= Q(
                tracing_number=statement.tracing_number,
            )

        if statement.api_response.get('ref1', None):
            same_reference_numbers_within_the_same_provider_query_conditions &= Q(
                api_response__has_key='ref1',
                api_response__ref1=statement.api_response['ref1'],
            )

        if statement.api_response.get('ref2', None):
            same_reference_numbers_within_the_same_provider_query_conditions &= Q(
                api_response__has_key='ref2',
                api_response__ref2=statement.api_response['ref2'],
            )

        if statement.api_response.get('bankTransactionId', None):
            same_reference_numbers_within_the_same_provider_query_conditions &= Q(
                api_response__has_key='bankTransactionId',
                api_response__bankTransactionId=statement.api_response['bankTransactionId'],
            )

        same_reference_numbers_within_different_providers_query_conditions = ~Q(
            destination_account__provider=statement.destination_account.provider,
        )

        if statement.tracing_number:
            same_reference_numbers_within_different_providers_query_conditions &= Q(
                tracing_number=statement.tracing_number,
            )

        if statement.api_response.get('ref1', None):
            same_reference_numbers_within_different_providers_query_conditions &= Q(
                api_response__has_key='bankTransactionId',
                api_response__bankTransactionId=statement.api_response['ref1'],
            )

        if statement.api_response.get('bankTransactionId', None):
            same_reference_numbers_within_different_providers_query_conditions &= Q(
                api_response__has_key='ref1',
                api_response__ref1=statement.api_response['bankTransactionId'],
            )

        possible_double_spend_query_conditions = (
            Q(destination_account__iban=statement.destination_account.iban, amount=statement.amount)
            & same_source_query_conditions
            & (
                same_reference_numbers_within_the_same_provider_query_conditions
                | same_reference_numbers_within_different_providers_query_conditions
            )
        )

        return CoBankStatement.objects.filter(possible_double_spend_query_conditions).exclude(pk=statement.pk)


class RefundStatementValidator(Validator):
    error = RefundValidationException

    def _validate(self, obj):
        if not obj or not isinstance(obj, CoBankStatement):
            raise self.error('ObjectIsNotValid')

        if STATEMENT_STATUS.refunded not in CoBankStatement.POSSIBLE_STATUS_TRANSITIONS[obj.status]:
            raise self.error('ObjectStatusNotValidToRefund')

        if not obj.is_deposit:
            raise self.error('StatementIsNotDeposit')

        if not obj.destination_account.iban:
            raise self.error('StatementDestinationAccountWithoutIBAN')

        if not obj.provider_statement_id:
            raise self.error('StatementWithoutProviderStatementID')

        return obj
