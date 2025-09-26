import copy
import datetime
import decimal
import functools
import uuid
from decimal import Decimal
from json import JSONDecodeError

from django.contrib.postgres.fields import ArrayField
from django.db import IntegrityError, models, transaction
from django.db.models import JSONField, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from model_utils import Choices
from requests import HTTPError

from exchange import settings
from exchange.accounts.models import User
from exchange.base.calendar import get_earliest_time, ir_now
from exchange.base.constants import ZERO
from exchange.base.crypto import unique_random_string
from exchange.base.logging import report_exception
from exchange.base.models import RIAL, Settings
from exchange.base.parsers import parse_choices
from exchange.base.tasks import run_admin_task
from exchange.direct_debit.constants import CONTRACT_EXPIRES_AT_OFFSET_MINUTES, DEFAULT_MIN_DEPOSIT_AMOUNT
from exchange.direct_debit.exceptions import (
    ContractEndDateError,
    ContractIntegrityError,
    ContractStartDateError,
    ContractStatusError,
    DailyMaxTransactionCountError,
    DirectDebitBankNotActiveError,
    DirectDebitBankNotFoundError,
    MaxAmountBankExceededError,
    MaxAmountExceededError,
    MaxDailyAmountExceededError,
    MaxDailyCountExceededError,
    MaxTransactionAmountError,
    MinAmountNotMetError,
    StatusUnchangedError,
    ThirdPartyClientError,
    ThirdPartyConnectionError,
    ThirdPartyError,
)
from exchange.direct_debit.integrations.faraboom import FaraboomHandler
from exchange.direct_debit.managers import DirectDebitContractManager
from exchange.direct_debit.notifications import (
    AutoContractCanceledNotification,
    ContractSuccessfullyCreatedNotification,
    ContractSuccessfullyEditedNotification,
    ContractSuccessfullyRemovedNotification,
    CreateContractFailedNotification,
    DirectDepositFailedNotification,
    DirectDepositSuccessfulNotification,
    EditContractFailedNotification,
    RemoveContractFailedNotification,
)
from exchange.direct_debit.types import get_deposit_response_object
from exchange.wallet.models import Transaction, Wallet


class DirectDebitBank(models.Model):
    is_active = models.BooleanField(default=True)
    bank_id = models.CharField(max_length=25, unique=True, db_index=True)
    name = models.CharField(max_length=50, null=False)
    daily_max_transaction_amount = models.DecimalField(max_digits=30, decimal_places=10)
    daily_max_transaction_count = models.IntegerField(default=0)
    max_transaction_amount = models.DecimalField(max_digits=30, decimal_places=10, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'بانک دایرکت دبیت'
        verbose_name_plural = verbose_name

    def save(self, *args, update_fields=None, **kwargs):
        if self.pk is not None:
            self.updated_at = ir_now()
            if update_fields:
                update_fields = (*update_fields, 'updated_at')

        super().save(*args, update_fields=update_fields, **kwargs)


ContractStatus = Choices(
    (0, 'created', 'Created'),
    (1, 'initializing', 'Initializing'),
    (2, 'waiting_for_confirm', 'Waiting for confirmation'),
    (3, 'active', 'Active'),
    (4, 'cancelled', 'Cancelled'),
    (5, 'expired', 'Expired'),
    (6, 'failed', 'Failed'),
    (7, 'deactive', 'Deactive'),
    (8, 'waiting_for_update', 'Waiting for update'),
    (9, 'replaced', 'Replaced'),
    (10, 'failed_update', 'Failed update'),
)


class DirectDebitContract(models.Model):
    objects = DirectDebitContractManager()

    STATUS = ContractStatus

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    status = models.SmallIntegerField(choices=STATUS, default=STATUS.created)
    user = models.ForeignKey(User, related_name='direct_debit_contracts', on_delete=models.CASCADE)
    bank = models.ForeignKey(DirectDebitBank, related_name='direct_debit_contracts', on_delete=models.PROTECT)
    contract_code = models.CharField(max_length=50)
    contract_id = models.CharField(max_length=50)
    bank_account_number = models.CharField(max_length=50)
    trace_id = models.CharField(max_length=50, null=False, db_index=True)
    started_at = models.DateTimeField(null=True)
    expires_at = models.DateTimeField(null=False, verbose_name='تاریخ انقضا')
    daily_max_transaction_count = models.IntegerField(default=0, verbose_name='سقف تعداد تراکنش روزانه')
    max_transaction_amount = models.DecimalField(
        max_digits=30, decimal_places=10, null=True, blank=True, verbose_name='حداکثر مقدار تراکنش'
    )
    location = models.CharField(max_length=1000, default='')

    class Meta:
        verbose_name = 'پیمان واریز مستقیم'
        verbose_name_plural = verbose_name
        constraints = (
            models.UniqueConstraint(
                fields=['user', 'bank'],
                condition=Q(
                    status__in=[
                        ContractStatus.active,
                        ContractStatus.initializing,
                        ContractStatus.waiting_for_confirm,
                    ],
                ),
                name='unique_user_and_bank',
            ),
        )

    @property
    def user_code(self):
        return f'{self.id}-{self.user.id}'

    @classmethod
    def create(
        cls,
        user: User,
        bank_id: int,
        to_date: datetime,
        daily_max_transaction_count: int,
        max_transaction_amount: Decimal,
        from_date: datetime = None,
    ) -> 'DirectDebitContract':
        _now = ir_now()
        trace_id = str(unique_random_string())
        _from_date = timezone.make_aware(
            timezone.datetime.combine(from_date or ir_now(), (ir_now() + datetime.timedelta(minutes=1)).time())
        )
        start_date = _from_date
        aware_datetime = timezone.make_aware(timezone.datetime.combine(to_date, ir_now().time()))
        end_date = aware_datetime - datetime.timedelta(minutes=CONTRACT_EXPIRES_AT_OFFSET_MINUTES)

        if start_date < _now:
            raise ContractStartDateError

        if end_date <= start_date:
            raise ContractEndDateError

        bank: DirectDebitBank = DirectDebitBank.objects.filter(pk=bank_id).first()
        if not bank:
            raise DirectDebitBankNotFoundError
        if not bank.is_active:
            raise DirectDebitBankNotActiveError

        if cls.objects.filter(
            bank=bank,
            user=user,
            status__in=(cls.STATUS.active, cls.STATUS.initializing, cls.STATUS.waiting_for_confirm),
        ).exists():
            raise ContractIntegrityError

        if (
            max_transaction_amount
            and bank.max_transaction_amount
            and max_transaction_amount > bank.max_transaction_amount
        ):
            raise MaxTransactionAmountError

        # the default 0 of bank.daily_max_transaction_count means the bank doesn't have limit for it
        if ZERO < bank.daily_max_transaction_count < daily_max_transaction_count:
            raise DailyMaxTransactionCountError

        try:
            contract = cls.objects.create(
                user=user,
                bank=bank,
                trace_id=trace_id,
                started_at=start_date,
                expires_at=end_date,
                daily_max_transaction_count=daily_max_transaction_count,
                max_transaction_amount=max_transaction_amount,
            )
            response = FaraboomHandler.create_contract(contract=contract)
            if response.status_code == 302:
                location = response.headers['Location']
                if location is not None:
                    contract.set_location(location)
                    return contract
        except HTTPError as e:
            try:
                response = e.response.json()
            except JSONDecodeError:
                raise ThirdPartyClientError from e
            raise ThirdPartyError(code=response.get('code')) from e
        except IntegrityError as e:
            raise ContractIntegrityError from e
        except Exception as e:
            report_exception()  # TODO: Remove after test
            raise ThirdPartyClientError from e

    def set_location(self, location: str):
        self.location = location
        self.status = self.STATUS.initializing
        self.save(update_fields=['location', 'status'])

    def cancel(self):
        self.status = self.STATUS.cancelled
        self.save(update_fields=['status'])

    def notify(self):
        if self.status == self.STATUS.active:
            ContractSuccessfullyCreatedNotification(user=self.user).send(
                bank_name=self.bank.name,
                expires_at=self.expires_at,
                max_amount=self.max_transaction_amount,
            )
        elif self.status == self.STATUS.cancelled:
            ContractSuccessfullyRemovedNotification(user=self.user).send(
                bank_name=self.bank.name,
            )

    def notify_on_error(self, state: str = 'create'):
        if state == 'create' and self.status in (
            self.STATUS.created,
            self.STATUS.initializing,
            self.STATUS.waiting_for_confirm,
            self.STATUS.failed,
        ):
            CreateContractFailedNotification(user=self.user).send(bank_name=self.bank.name)
        elif state == 'cancel':
            RemoveContractFailedNotification(user=self.user).send(bank_name=self.bank.name)
        elif state == 'update':
            pass

    def notify_edited_successfully(self, old_contract: 'DirectDebitContract'):
        target_fields = ('expires_at', 'daily_max_transaction_count', 'max_transaction_amount')
        fields = [field for field in self._meta.get_fields(include_parents=False) if field.name in target_fields]
        edited_fields = filter(
            lambda field: getattr(old_contract, field.name, None) != getattr(self, field.name, None), fields
        )
        edited_fields_title = ', '.join([field.verbose_name for field in edited_fields])

        ContractSuccessfullyEditedNotification(user=self.user).send(
            bank_name=self.bank.name, edited_fields=edited_fields_title
        )

    def notify_edit_failed(self):
        EditContractFailedNotification(user=self.user).send(bank_name=self.bank.name)

    def activate(self):
        response = FaraboomHandler().activate_contract(contract_code=self.contract_code, bank_id=self.bank.bank_id)
        contract_id = None
        if response.status_code == 200:
            json_response = response.json()
            contract_id = json_response.get('payman_id')
        if contract_id:
            self.contract_id = contract_id
            self.status = DirectDebitContract.STATUS.active
            self.save(update_fields=['contract_id', 'status'])
            transaction.on_commit(lambda: self.notify())

    def update_contract(
        self,
        expires_at: datetime = None,
        daily_max_transaction_count: int = None,
        max_transaction_amount: decimal.Decimal = None,
    ):

        new_contract = copy.deepcopy(self)
        new_contract.id = None
        new_contract.status = self.STATUS.waiting_for_update
        new_contract.created_at = ir_now()
        new_contract.expires_at = (
            (expires_at - datetime.timedelta(minutes=CONTRACT_EXPIRES_AT_OFFSET_MINUTES))
            if expires_at
            else self.expires_at
        )
        new_contract.daily_max_transaction_count = daily_max_transaction_count or self.daily_max_transaction_count
        new_contract.max_transaction_amount = max_transaction_amount or self.max_transaction_amount
        new_contract.save()

        if expires_at and expires_at <= ir_now():
            raise ContractEndDateError

        # the default 0 of bank.daily_max_transaction_count means the bank doesn't have limit for it
        if daily_max_transaction_count and ZERO < self.bank.daily_max_transaction_count < daily_max_transaction_count:
            raise DailyMaxTransactionCountError

        if (
            max_transaction_amount
            and self.bank.max_transaction_amount
            and ZERO < self.bank.max_transaction_amount < max_transaction_amount
        ):
            raise MaxTransactionAmountError
        try:
            response = FaraboomHandler().update_contract(new_contract)
            if response.status_code == 302:
                location = response.headers['Location']
                new_contract.location = location
                new_contract.save(update_fields=['location'])
                return location
        except HTTPError as e:
            response = e.response.json()
            raise ThirdPartyError(code=response.get('code')) from e
        except Exception as e:
            report_exception()  # TODO: Remove after test
            raise ThirdPartyClientError from e

    def is_max_daily_contract_transaction_count_reached(self) -> bool:
        midnight = get_earliest_time(ir_now())
        deposit_count = DirectDeposit.objects.filter(contract=self, deposited_at__gte=midnight).count()
        if 0 < self.daily_max_transaction_count < deposit_count + 1:
            return True
        return False

    def is_max_daily_contract_transaction_amount_reached(self, amount: decimal.Decimal) -> bool:
        midnight = get_earliest_time(ir_now())
        total_deposit_amount = DirectDeposit.objects.filter(contract=self, deposited_at__gte=midnight).aggregate(
            total=Coalesce(Sum('amount'), ZERO),
        )['total']
        if total_deposit_amount + amount > self.bank.daily_max_transaction_amount:
            return True
        return False

    def is_max_transaction_amount_reached(self, amount: decimal.Decimal) -> bool:
        return self.max_transaction_amount and self.max_transaction_amount < amount

    def is_max_transaction_amount_bank_reached(self, amount: decimal.Decimal) -> bool:
        if self.bank.max_transaction_amount and amount > self.bank.max_transaction_amount:
            return True
        return False

    @staticmethod
    def is_amount_less_that_min(amount: decimal.Decimal) -> bool:
        return amount < decimal.Decimal(Settings.get('direct_debit_min_amount_in_deposit', DEFAULT_MIN_DEPOSIT_AMOUNT))

    def validate_deposit_request(self, amount):
        if self.is_max_daily_contract_transaction_amount_reached(amount):
            raise MaxDailyAmountExceededError
        if self.is_max_daily_contract_transaction_count_reached():
            raise MaxDailyCountExceededError
        if self.is_max_transaction_amount_reached(amount):
            raise MaxAmountExceededError
        if self.is_max_transaction_amount_bank_reached(amount):
            raise MaxAmountBankExceededError
        if self.is_amount_less_that_min(amount):
            raise MinAmountNotMetError

    def deposit(self, amount: decimal.Decimal):
        failure_notifier = DirectDepositFailedNotification(self.user)

        self.validate_deposit_request(amount)
        trace_id = uuid.uuid4().hex
        with transaction.atomic():
            deposit = DirectDeposit.objects.create(
                trace_id=trace_id,
                contract=self,
                amount=amount,
            )
        try:
            response = FaraboomHandler.direct_deposit(
                trace_id=trace_id,
                contract_id=self.contract_id,
                amount=amount,
                bank_id=self.bank.bank_id,
                description='Nobitex Direct Debit Transaction',
            )
            response_data = response.json()

        except ThirdPartyConnectionError as e:
            self._handle_deposit_exception(
                deposit,
                status=DirectDeposit.STATUS.timeout,
                error_details={'error_response': str(e.__cause__) or str(e)},
                notifier=failure_notifier,
            )
            raise ThirdPartyClientError from e

        except HTTPError as e:
            failure_notifier.send(self.bank.name)
            response_data = self._parse_error_response(e)
            error_code = response_data.get('code', None)
            if error_code:
                if error_code == '003':  # user has not enough balance error
                    self.perform_low_balance_action(deposit, response_data)
                elif error_code in ['2154', '2010', '2213']:  # contract deactivate in bank
                    self.deactivate_in_provider()
                    self._handle_deposit_exception(deposit, DirectDeposit.STATUS.failed, response_data)
                else:
                    self._handle_deposit_exception(deposit, DirectDeposit.STATUS.failed, response_data)
                raise ThirdPartyError(code=error_code) from e

            self._handle_deposit_exception(
                deposit,
                DirectDeposit.STATUS.failed,
                {'error_response': e.response.text or str(e)},
            )
            raise ThirdPartyClientError from e
        except Exception as e:
            self._handle_deposit_exception(
                deposit,
                DirectDeposit.STATUS.failed,
                {'error_response': str(e)},
                notifier=failure_notifier,
            )
            report_exception()  # TODO: Remove after test
            raise ThirdPartyClientError from e

        deposit_update_data = get_deposit_response_object(response).prepare_for_update()
        deposit_update_data['third_party_response'] = response_data
        self._finalize_deposit(deposit, deposit_update_data)
        return deposit

    def _handle_deposit_exception(self, deposit, status, error_details, notifier=None):
        self._update_deposit_status(deposit, status, error_details)
        if notifier:
            notifier.send(self.bank.name)

    def _parse_error_response(self, exception):
        try:
            return exception.response.json()
        except ValueError:
            return {'error': exception.response.text or 'No response content'}

    def perform_low_balance_action(self, deposit: 'DirectDeposit', response_data):
        """
        If the user does not have enough balance for period_days days after max_count attempts,
         we will be inactive their contract
        """
        from exchange.direct_debit.tasks import task_cancel_contract_in_provider

        self._handle_deposit_exception(deposit, DirectDeposit.STATUS.insufficient_balance, response_data)

        max_count = int(Settings.get('direct_debit_insufficient_balance_max_count', 3))
        period_days = int(Settings.get('direct_debit_insufficient_balance_period_days', 5))
        insufficient_count = DirectDeposit.objects.filter(
            contract=self,
            status=DirectDeposit.STATUS.insufficient_balance,
            created_at__gte=ir_now() - datetime.timedelta(days=period_days),
        ).count()
        if insufficient_count >= max_count:
            self.status = self.STATUS.cancelled
            self.save(update_fields=['status'])
            transaction.on_commit(lambda: AutoContractCanceledNotification(self.user).send(self.bank.name))
            transaction.on_commit(
                functools.partial(
                    task_cancel_contract_in_provider.apply_async,
                    args=(self.contract_id, self.bank.bank_id),
                )
            )

    def deactivate_in_provider(self):
        from exchange.direct_debit.tasks import task_deactivate_contract_in_provider

        transaction.on_commit(
            functools.partial(
                task_deactivate_contract_in_provider.apply_async,
                args=(self.contract_id, self.bank.bank_id, self.bank.name, self.user.id),
            )
        )

    def check_eligibility_to_change_status(self, new_status: int):
        accepted_new_status = [self.STATUS.active, self.STATUS.deactive, self.STATUS.cancelled]
        if new_status not in accepted_new_status:
            raise ValueError('The new status is not valid')

        if new_status == self.status:
            raise ValueError('Cannot change contract status to the same status.')

        # cancel the contract is ok even when the bank is disabled
        if new_status != self.STATUS.cancelled and self.bank.is_active is False:
            raise DirectDebitBankNotActiveError

        if (
            new_status == self.STATUS.active
            and DirectDebitContract.objects.filter(bank=self.bank, user=self.user, status=self.STATUS.active).exists()
        ):
            raise ContractIntegrityError

        if self.status in [
            self.STATUS.cancelled,
            self.STATUS.failed,
            self.STATUS.expired,
        ]:
            raise ContractStatusError()

    def change_status(self, new_status: str):
        _new_status_id = parse_choices(self.STATUS, new_status, required=True)

        def notify_on_cancel():
            if _new_status_id == self.STATUS.cancelled:
                self.notify_on_error('cancel')

        self.check_eligibility_to_change_status(new_status=_new_status_id)
        try:
            response = FaraboomHandler().change_contract_status(self.contract_id, new_status, self.bank.bank_id)
        except HTTPError as e:
            notify_on_cancel()
            response = e.response.json()
            raise ThirdPartyError(code=response.get('code')) from e
        except Exception as e:
            notify_on_cancel()
            report_exception()  # TODO: Remove after test
            raise ThirdPartyClientError from e

        changed_status = None
        if response.status_code == 200:
            changed_status = response.json().get('status', '').lower()
            if changed_status != new_status:
                notify_on_cancel()
                raise StatusUnchangedError
            self.status = _new_status_id
            self.save(update_fields=['status'])
            transaction.on_commit(lambda: self.notify())
        return changed_status

    def _finalize_deposit(
        self,
        deposit: 'DirectDeposit',
        deposit_update_data: dict,
    ):
        with transaction.atomic():
            for field, value in deposit_update_data.items():
                setattr(deposit, field, value)
            deposit.fee = DirectDeposit.calculate_fee(deposit.amount)
            deposit.deposited_at = ir_now()
            deposit.third_party_response = deposit_update_data.get('third_party_response', {})
            update_fields = list(deposit_update_data.keys()) + ['fee', 'deposited_at', 'third_party_response']
            deposit.save(update_fields=update_fields)
            deposit.commit_deposit()

            success_notifier = DirectDepositSuccessfulNotification(self.user)
            transaction.on_commit(lambda: success_notifier.send(deposit.transaction.amount, self.bank.name))

    def _update_deposit_status(self, deposit, status, response_data):
        deposit.third_party_response = response_data
        deposit.status = status
        deposit.save(update_fields=['third_party_response', 'status'])


class DirectDeposit(models.Model):
    STATUS = Choices(
        (0, 'in_progress', 'In progress'),
        (1, 'failed', 'Failed'),
        (2, 'succeed', 'Succeed'),
        (3, 'reversed', 'Reversed'),
        (4, 'timeout', 'Timeout'),
        (5, 'insufficient_balance', 'Insufficient balance'),
    )
    status = models.PositiveSmallIntegerField(choices=STATUS, default=STATUS.in_progress)
    created_at = models.DateTimeField(auto_now_add=True)
    trace_id = models.CharField(max_length=100, db_index=True)
    deposited_at = models.DateTimeField(db_index=True, null=True)
    contract = models.ForeignKey(DirectDebitContract, related_name='direct_deposits', on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=30, decimal_places=10, null=True, blank=True)
    fee = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    transaction = models.ForeignKey(Transaction, null=True, blank=True, on_delete=models.CASCADE)
    reference_id = models.CharField(max_length=100, default='')
    batch_id = models.CharField(max_length=100, default='')
    details = ArrayField(JSONField(null=True, blank=True), null=True, blank=True)
    third_party_response = models.JSONField(default=dict, blank=True)

    USER_VISIBLE_STATUES = [
        STATUS.failed,
        STATUS.succeed,
        STATUS.reversed,
        STATUS.timeout,
        STATUS.insufficient_balance,
    ]

    class Meta:
        verbose_name = 'واریز مستقیم'
        verbose_name_plural = verbose_name

    @property
    def effective_date(self):
        if self.transaction:
            return self.transaction.created_at
        return self.created_at

    @property
    def net_amount(self):
        return self.amount - self.fee

    @classmethod
    def calculate_fee(cls, amount: Decimal) -> Decimal:
        direct_debit_fee = settings.NOBITEX_OPTIONS['directDebitFee']
        min_fee = direct_debit_fee['min']
        max_fee = direct_debit_fee['max']

        fee = int(amount * direct_debit_fee['rate'])

        if fee < min_fee:
            fee = min_fee
        elif fee > max_fee:
            fee = max_fee

        return Decimal(fee)

    def commit_deposit(self):
        if self.transaction:
            return True
        # Create transaction and set fee
        wallet = Wallet.get_user_wallet(self.contract.user, RIAL)
        description = f'واریز مستقیم - {self.contract.bank.name} - شماره پیگیری: {self.trace_id}'
        is_amount_positive = self.amount > 0
        wallet_transaction = wallet.create_transaction(
            tp='deposit',
            amount=self.net_amount,
            description=description,
            allow_negative_balance=is_amount_positive,
        )
        wallet_transaction.commit(
            allow_negative_balance=is_amount_positive,
            ref=Transaction.Ref('DirectDebitUserTransaction', self.pk),
        )
        self.transaction = wallet_transaction
        self.status = self.STATUS.succeed
        self.save(update_fields=['transaction', 'status'])
        if not Settings.is_disabled('detect_direct_deposit_for_fraud'):
            transaction.on_commit(
                lambda: run_admin_task('detectify.check_direct_deposit_fraud', direct_deposit_id=self.pk)
            )
        return True


class DailyDirectDeposit(models.Model):
    STATUS = Choices(
        (0, 'in_progress', 'IN_PROGRESS'),
        (1, 'failed', 'FAILED'),
        (2, 'succeed', 'SUCCEED'),
        (3, 'reversed', 'REVERSED'),
        (4, 'timeout', 'TIMEOUT'),
        (5, 'insufficient_balance', 'Insufficient balance'),
    )
    STATUSES_TRANSIENT = (STATUS.in_progress,)
    description = models.CharField(max_length=200, null=True, blank=True)
    transaction_amount = models.DecimalField(max_digits=30, decimal_places=10, null=True, blank=True)
    destination_bank = models.CharField(max_length=100, null=True, blank=True)
    reference_id = models.CharField(max_length=100, null=True, blank=True)
    source_bank = models.CharField(max_length=100, null=True, blank=True)
    status = models.PositiveSmallIntegerField(choices=STATUS, default=STATUS.in_progress)
    trace_id = models.CharField(max_length=100, null=True, blank=True, db_index=True, unique=True)
    contract_id = models.CharField(max_length=100, null=True, blank=True)
    transaction_type = models.CharField(max_length=100, null=True, blank=True)
    server_date = models.DateTimeField(null=True, blank=True)
    client_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    deposit = models.OneToOneField(DirectDeposit, null=True, on_delete=models.CASCADE)

