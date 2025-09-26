from collections import defaultdict
from typing import Iterable, List, Optional, Tuple, Union

from django.db import models, transaction
from django.db.models import QuerySet
from django.db.models.query_utils import Q

from exchange.accounts.models import BankAccount, Notification, UserSms
from exchange.base.calendar import ir_tz
from exchange.base.formatting import format_money
from exchange.base.logging import log_time_without_avg, metric_incr, report_exception
from exchange.base.models import RIAL
from exchange.corporate_banking.exceptions import MultipleBankAccountFound, NoBankAccountFound
from exchange.corporate_banking.models import (
    ACCOUNT_TP,
    BANK_ID_TO_ENGLISH_NAME,
    REJECTION_REASONS,
    STATEMENT_STATUS,
    STATEMENT_TYPE,
    CoBankStatement,
    CoBankUserDeposit,
)
from exchange.corporate_banking.services.refunder import Refunder
from exchange.corporate_banking.services.validators import (
    BankAccountValidator,
    DepositAmountValidator,
    DoubleSpendPreventer,
    FeatureFlagValidator,
    UserLevelValidator,
    Validator,
)


class Settler:

    def __init__(self, settling_pending_deposits: bool = False):
        self.settling_pending_deposits = settling_pending_deposits
        self.metric_name = 'metric_cobanking_core_services_count'

    def settle_statements(self):
        deposits = self._get_deposits_to_settle()
        valid_deposits = self.validate_deposits(deposits)
        executed_deposits = []
        for deposit in valid_deposits:
            try:
                executed_deposits.append(self.create_deposit(deposit))
            except:
                report_exception()
        self._increase_deposit_metrics([deposit.cobank_statement for deposit in executed_deposits])
        self._log_deposit_lag_metric(executed_deposits)

    def validate_deposits(
        self,
        deposits: Union[QuerySet, List[models.Model]],
        bypass_high_amount: bool = False,
        ignore_double_spend: bool = False,
    ) -> List[CoBankStatement]:
        # Here we will not change the rejection reason of a previously pending or rejected statement for now
        validators = self._get_validators(bypass_high_amount, ignore_double_spend)
        valid_statements, requiring_admin_approval, rejected = [], [], []

        for deposit in deposits:
            state, reason = self.examine_deposit(validators, deposit)
            if state == STATEMENT_STATUS.validated:
                deposit.status = STATEMENT_STATUS.validated
                valid_statements.append(deposit)
            elif state == STATEMENT_STATUS.pending_admin:
                deposit.status = STATEMENT_STATUS.pending_admin
                deposit.rejection_reason = reason
                requiring_admin_approval.append(deposit)
            elif state == STATEMENT_STATUS.rejected:
                deposit.status = STATEMENT_STATUS.rejected
                deposit.rejection_reason = reason
                rejected.append(deposit)

        CoBankStatement.objects.bulk_update(requiring_admin_approval + rejected, fields=['status', 'rejection_reason'])
        self._increase_deposit_metrics(valid_statements + requiring_admin_approval + rejected)
        return valid_statements

    def examine_deposit(self, validators: List[Validator], deposit: CoBankStatement) -> Tuple[int, Optional[int]]:
        for validator in validators:
            try:
                validator.validate(deposit)
            except DepositAmountValidator.error as e:
                if e.code == 'AmountTooHigh':
                    return STATEMENT_STATUS.pending_admin, REJECTION_REASONS.unacceptable_amount
                elif e.code == 'AmountTooLow':
                    return STATEMENT_STATUS.rejected, REJECTION_REASONS.unacceptable_amount
            except BankAccountValidator.error as e:
                if e.code == 'EmptyIban':
                    return STATEMENT_STATUS.pending_admin, REJECTION_REASONS.empty_source_account
                elif e.code == 'BankAccountNotFound':
                    return STATEMENT_STATUS.pending_admin, REJECTION_REASONS.source_account_not_found
                elif e.code == 'SharedBankAccount':
                    return STATEMENT_STATUS.rejected, REJECTION_REASONS.shared_source_account
            except UserLevelValidator.error as e:
                if e.code == 'IneligibleUser':
                    return STATEMENT_STATUS.rejected, REJECTION_REASONS.ineligible_user
                elif e.code == 'UserNotFound':
                    return STATEMENT_STATUS.rejected, REJECTION_REASONS.user_not_found
            except FeatureFlagValidator.error as e:
                if e.code == 'FeatureUnavailable':
                    return STATEMENT_STATUS.pending_admin, REJECTION_REASONS.no_feature_flag
                elif e.code == 'UserNotFound':
                    return STATEMENT_STATUS.rejected, REJECTION_REASONS.user_not_found
            except DoubleSpendPreventer.error as e:
                if e.code == 'RepeatedReferenceCode':
                    return STATEMENT_STATUS.pending_admin, REJECTION_REASONS.repeated_reference_code
                elif e.code == 'OldTransaction':
                    return STATEMENT_STATUS.pending_admin, REJECTION_REASONS.old_transaction
            except Exception:
                return STATEMENT_STATUS.rejected, REJECTION_REASONS.other
        return STATEMENT_STATUS.validated, None

    @transaction.atomic
    def create_deposit(self, statement: CoBankStatement, update_fields: Iterable[str] = None):
        update_fields = update_fields if update_fields else []
        if statement.source_iban:
            source_bank_account = self.get_bank_account(statement.source_iban)
        else:
            raise ValueError('Source IBAN not found')
        deposit = CoBankUserDeposit.objects.create(
            cobank_statement=statement,
            user=source_bank_account.user,
            user_bank_account=source_bank_account,
            amount=statement.amount,
        )
        statement.status = STATEMENT_STATUS.executed
        statement.save(update_fields=('status', *update_fields))

        transaction.on_commit(lambda: self.notify(deposit))
        return deposit

    def get_bank_account(self, sheba_number: str) -> Optional[BankAccount]:
        bank_accounts = BankAccount.objects.filter(confirmed=True, shaba_number=sheba_number)
        # This should not ever happen because of BankAccountValidator
        if len(bank_accounts) > 1 and len(bank_accounts.values('user').distinct()) > 1:
            raise MultipleBankAccountFound('MultipleBankAccountFound')

        # This only will happen in case of race condition between cron and delete bank account
        if len(bank_accounts) == 0:
            raise NoBankAccountFound('NoBankAccountFound')

        if isinstance(bank_accounts, QuerySet) and len(bank_accounts) > 1:
            return bank_accounts.filter(is_deleted=False).first() or bank_accounts.first()
        return bank_accounts.first()

    def notify(self, deposit: CoBankUserDeposit):
        amount = format_money(money=deposit.amount, currency=RIAL)
        bank_name = deposit.user_bank_account.get_bank_id_display()
        Notification.objects.create(
            user=deposit.user,
            message=f'{amount} تومان از مبداء بانک {bank_name} به کیف اسپات شما در نوبیتکس واریز شد.',
        )
        if deposit.user.get_verification_profile().mobile_confirmed:
            UserSms.objects.create(
                user=deposit.user,
                tp=UserSms.TYPES.cobank_deposit,
                to=deposit.user.mobile,
                template=UserSms.TEMPLATES.cobank_deposit,
                text=amount + '\n' + bank_name,
            )

    @transaction.atomic
    def change_statement_status(self, statement_pk: int, changes: dict):
        statement = CoBankStatement.objects.filter(pk=statement_pk).first()
        if not statement:
            return
        if 'status' not in changes or changes['status'] == statement.status:
            self._update_iban_if_needed(statement, changes)
            return
        if changes['status'] not in CoBankStatement.POSSIBLE_STATUS_TRANSITIONS[statement.status]:
            return
        if statement.status == STATEMENT_STATUS.new and changes['status'] == STATEMENT_STATUS.executed:
            return

        if statement.status == STATEMENT_STATUS.rejected and changes['status'] == STATEMENT_STATUS.refunded:
            self._refund_statement(statement)
            return

        if statement.status != STATEMENT_STATUS.pending_admin or (
            statement.status == STATEMENT_STATUS.pending_admin and changes['status'] == STATEMENT_STATUS.rejected
        ):
            statement.status = changes['status']
            statement.save(update_fields=('status',))
            return

        # The admin wants to change a statement in pending_admin status to executed
        if 'source_iban' in changes:
            statement.source_iban = changes['source_iban']

        bypass_high_amount = statement.rejection_reason == REJECTION_REASONS.unacceptable_amount
        ignore_double_spend = statement.rejection_reason in {
            REJECTION_REASONS.repeated_reference_code,
            REJECTION_REASONS.old_transaction,
        }

        valid_deposits = self.validate_deposits(
            [statement], bypass_high_amount=bypass_high_amount, ignore_double_spend=ignore_double_spend
        )
        if not valid_deposits:
            return
        self.create_deposit(valid_deposits[0], update_fields=('source_iban',))

    def _get_deposits_to_settle(self) -> QuerySet:
        if not self.settling_pending_deposits:
            return (
                CoBankStatement.objects.filter(
                    tp=STATEMENT_TYPE.deposit,
                    status=STATEMENT_STATUS.new,
                    destination_account__account_tp=ACCOUNT_TP.operational,
                )
                .exclude(
                    Q(source_iban__isnull=True) | Q(source_iban=''),
                )
                .select_related('destination_account')
            )
        return CoBankStatement.objects.filter(
            Q(
                status=STATEMENT_STATUS.pending_admin,
                rejection_reason__in=CoBankStatement.REASONS_FOR_AUTOMATIC_STATUS_CHECK,
            )
            | Q(status=STATEMENT_STATUS.rejected, rejection_reason=REJECTION_REASONS.ineligible_user),
            tp=STATEMENT_TYPE.deposit,
            destination_account__account_tp=ACCOUNT_TP.operational,
        ).select_related('destination_account')

    def _get_validators(self, bypass_high_amount: bool = False, ignore_double_spend: bool = False) -> List[Validator]:
        validator = UserLevelValidator(
            FeatureFlagValidator(BankAccountValidator(DepositAmountValidator(None, bypass_high_amount)))
        )
        if ignore_double_spend:
            return [validator]
        return [validator, DoubleSpendPreventer()]

    def _increase_deposit_metrics(self, statements: [CoBankStatement]):
        statements_by_metric_labels = {}
        for statement in statements:
            provider = statement.destination_account.get_provider_display()
            bank_name = BANK_ID_TO_ENGLISH_NAME[statement.destination_account.bank]
            status = ''
            if statement.status == STATEMENT_STATUS.executed:
                status = 'executed'
            elif statement.status == STATEMENT_STATUS.validated:
                status = 'valid'
            elif statement.status == STATEMENT_STATUS.rejected:
                status = 'rejected'
            elif statement.status == STATEMENT_STATUS.pending_admin:
                status = 'pendingAdmin'
            else:
                status = statement.get_status_display()
            statements_by_metric_labels[(provider, bank_name, status)] = (
                statements_by_metric_labels.get((provider, bank_name, status), 0) + 1
            )
        # Avoid recounting pending cases by every execution of the SettlePendingDepositsAutomaticallyCron
        if self.settling_pending_deposits and 'pendingAdmin' in statements_by_metric_labels:
            del statements_by_metric_labels['pendingAdmin']
        for labels, number in statements_by_metric_labels.items():
            metric_incr(self.metric_name, amount=number, labels=('deposits', *labels))

    def _log_deposit_lag_metric(self, executed_deposits: List[CoBankUserDeposit]):
        if not executed_deposits:
            return

        total_lag_per_bank = defaultdict(int)
        total_deposit_per_bank = defaultdict(int)

        for deposit in filter(lambda d: d.cobank_statement.transaction_datetime is not None, executed_deposits):
            bank = BANK_ID_TO_ENGLISH_NAME[deposit.cobank_statement.destination_account.bank]
            total_deposit_per_bank[bank] += 1
            total_lag_per_bank[bank] += (
                deposit.created_at.astimezone(ir_tz())
                - deposit.cobank_statement.transaction_datetime.astimezone(ir_tz())
            ).total_seconds()

        for bank in total_deposit_per_bank:
            avg_lag = int(total_lag_per_bank[bank] / total_deposit_per_bank[bank])
            log_time_without_avg(f'cobank_deposit_settlement_lag__{bank}', avg_lag)

    def _update_iban_if_needed(self, statement: CoBankStatement, changes: dict):
        is_permitted_status = statement.status in {STATEMENT_STATUS.new, STATEMENT_STATUS.pending_admin}
        if not statement.source_iban and 'source_iban' in changes and is_permitted_status:
            statement.source_iban = changes['source_iban']
            statement.save(update_fields=('source_iban',))

    def _refund_statement(self, statement: CoBankStatement):
        Refunder(provider=statement.destination_account.provider).refund_statement(statement)
