import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from django.db import IntegrityError, models, transaction
from django.db.models import Q, Sum
from model_utils import Choices, FieldTracker

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import (
    AmountIsLargerThanDebtOnUpdateUserService,
    ServiceAlreadyActivated,
    ServiceAlreadyDeactivated,
    UpdateClosedUserService,
)
from exchange.asset_backed_credit.models.service import Service, UserServicePermission
from exchange.asset_backed_credit.models.user import InternalUser
from exchange.base.calendar import ir_now
from exchange.base.constants import ZERO
from exchange.base.logging import report_event, report_exception
from exchange.base.money import money_is_zero


class UserService(models.Model):
    class Status(models.IntegerChoices):
        created = 0
        initiated = 10
        settled = 20
        expired = 30
        closed = 40
        close_requested = 50

    STATUS = Choices(
        (0, 'created', 'created'),
        (10, 'initiated', 'initiated'),
        (20, 'settled', 'settled'),
        (30, 'expired', 'expired'),
        (40, 'closed', 'closed'),
        (50, 'close_requested', 'close_requested'),
    )

    COLLATERAL_FEE_PERCENT = Decimal(0)
    COLLATERAL_FEE_AMOUNT = 0

    service = models.ForeignKey(Service, on_delete=models.CASCADE, verbose_name='سرویس اعتباری')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='کاربر')
    internal_user = models.ForeignKey(
        InternalUser,
        on_delete=models.CASCADE,
        verbose_name='کاربر',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(default=ir_now, verbose_name='تاریخ ایجاد')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ بسته شدن')
    current_debt = models.DecimalField(max_digits=30, decimal_places=10, verbose_name='بدهی فعلی')
    initial_debt = models.DecimalField(max_digits=30, decimal_places=10, verbose_name='بدهی اولیه')
    principal = models.DecimalField(max_digits=30, decimal_places=10, null=True, blank=True, verbose_name='مبلغ وام')
    installment_amount = models.DecimalField(
        max_digits=30, decimal_places=10, null=True, blank=True, verbose_name='مبلغ افساط'
    )
    installment_period = models.PositiveIntegerField(null=True, blank=True, verbose_name='مدت افساط')
    total_repayment = models.DecimalField(
        max_digits=30, decimal_places=10, null=True, blank=True, verbose_name='مبلغ بازپرداخت نهایی'
    )
    provider_fee_percent = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='هزینه سرویس دهنده به درصد'
    )
    provider_fee_amount = models.DecimalField(
        max_digits=30, decimal_places=10, null=True, blank=True, verbose_name='هزینه سرویس دهنده'
    )
    status = models.SmallIntegerField(choices=STATUS, default=STATUS.initiated, verbose_name='وضعیت')
    external_id = models.UUIDField(default=uuid.uuid4, editable=False)
    extra_info = models.JSONField(default=dict, blank=True)

    user_service_permission = models.OneToOneField(
        UserServicePermission,
        related_name='user_service',
        on_delete=models.PROTECT,
        verbose_name='مجوز',
    )
    account_number = models.CharField(blank=True, max_length=100, verbose_name='شماره کاربری')

    tracker = FieldTracker(fields=['current_debt', 'initial_debt'])

    class Meta:
        verbose_name = 'سرویس اعتباری کاربر'
        verbose_name_plural = 'سرویس اعتباری کاربر'
        constraints = (
            models.CheckConstraint(
                check=models.Q(current_debt__lte=models.F('initial_debt')),
                name='current_debt_limit',
            ),
            models.CheckConstraint(
                check=models.Q(current_debt__gte=ZERO),
                name='current_debt_positivity',
            ),
            models.UniqueConstraint(
                condition=models.Q(closed_at__isnull=True),
                fields=('user', 'service'),
                name='unique_active_user_service',
            ),
        )

    @property
    def is_revolving(self):
        return self.service.tp == Service.TYPES.debit

    @classmethod
    def get_total_active_debt(
        cls,
        user: User,
        service_provider: Optional[int] = None,
        service_type: Optional[int] = None,
    ) -> Decimal:
        """
        Calculate the total active debt for a given user, optional service-provider and service-type is available

        Parameters:
            user (User): The user for whom to calculate the total active debt.
            service_provider (int)
            service_type (int)

        Returns:
            Decimal: The total active debt for the specified user.

        If there is no active debt, the result is Decimal('0').
        """
        qs = cls.objects.filter(user=user, closed_at__isnull=True)
        if service_provider is not None:
            qs = qs.filter(service__provider=service_provider)
        if service_type is not None:
            qs = qs.filter(service__tp=service_type)

        return qs.aggregate(total=Sum('current_debt'))['total'] or Decimal('0')

    @classmethod
    def has_user_active_service(cls, user: User, service: Service = None) -> bool:
        """
        Check if a user has an active service.

        Parameters:
            - user (User): The user to check.
            - service (Service, optional): Specific service to check (default is None).

        Returns:
            bool: True if the user has an active service (or a specific service if provided),
                  False otherwise.

        Note:
            Excludes instances with statuses in the END_STATES attribute.
        """
        query = Q(user=user)
        if service:
            query &= Q(service=service)
        return cls.objects.filter(query, closed_at__isnull=True).exists()

    @classmethod
    def get_actives(cls, user: User):
        return cls.objects.filter(user=user, closed_at__isnull=True)

    def update_debt(self, amount: Decimal) -> None:
        """
        Update the initial and current debt with the given amount
        """
        self.assert_is_active()

        self.initial_debt += amount
        self.current_debt += amount
        if self.initial_debt < ZERO or self.current_debt < ZERO:
            raise AmountIsLargerThanDebtOnUpdateUserService('Amount exceeds user active debt.')

        self.save(update_fields=['initial_debt', 'current_debt'])

    def update_current_debt(self, amount: Decimal) -> None:
        """
        Update the current debt with the given amount
        """
        self.assert_is_active()

        self.current_debt += amount
        if self.current_debt < ZERO:
            raise AmountIsLargerThanDebtOnUpdateUserService('Amount exceeds user active debt.')

        self.save(update_fields=('current_debt',))

    @transaction.atomic
    def finalize(self, status: int, closed_at: Optional[datetime] = None, save=True) -> None:
        """
        finalize the current settlement of the user if the settlement is not closed before and has zero current debt

        Parameters:
            - status (int): the selected status of the finalized settlement
            - closed_at (Optional[datetime]): the closure date of the settlement
            - save (bool): save settlement
        """
        self.assert_is_active()

        if self.is_revolving or not money_is_zero(self.current_debt):
            return

        self.status = status
        self.closed_at = closed_at or ir_now()
        try:
            self.user_service_permission.deactivate()
        except ServiceAlreadyDeactivated:
            report_exception()
            pass

        if save:
            self.save(
                update_fields=(
                    'status',
                    'closed_at',
                )
            )

    def assert_is_active(self):
        if self.closed_at is not None:
            raise UpdateClosedUserService()

    @classmethod
    @transaction.atomic
    def activate(
        cls,
        user: User,
        internal_user: InternalUser,
        service: Service,
        initial_debt: Decimal,
        permission: 'UserServicePermission',
        account_number: Optional[str] = '',
        principal: Decimal = None,
        total_repayment: Decimal = None,
        installment_amount: Decimal = None,
        installment_period: int = None,
        provider_fee_percent: Decimal = None,
        provider_fee_amount: Decimal = None,
        extra_info: Optional[dict] = None,
    ) -> 'UserService':
        """
        Activates a user's service with the specified parameters.

        Args:
            user (User): The user for whom the service is being activated.
            internal_user (InternalUser): The user for whom the service is being activated.
            service (Service): The service to be activated for the user.
            initial_debt (Decimal): The amount associated with the service activation.
            permission (UserServicePermission): The permission for the user's service.
            account_number (Optional[str]): The account number of the user's service
            principal (Decimal): The principal for the user's service. (loan only)
            total_repayment (Decimal): The total repayment for the user's service. (loan only)
            installment_amount (Decimal): The installment amount for the user's service. (loan only)
            installment_period (int): The installment period for the user's service. (loan only)
            provider_fee_percent (Decimal): The provider-fee percent for the user's service. (loan only)
            provider_fee_amount (Decimal): The provider-fee amount for the user's service. (loan only)
            extra_info (dict): The extra info for the user's service.

        Returns:
            UserService: The activated user service instance.

        Raises:
            InsufficientCollateralError: If collateral is less than the amount to activate new service
            UserLimitExceededError: User cannot activate new service because it exceeds the limit
            ServiceAlreadyActivated: User cannot activate new service because it is already activated
                (unique on user and service)
            MinimumInitialDebtError: Amount is less than min_collateral.
        """

        try:
            return cls.objects.create(
                user=user,
                internal_user=internal_user,
                service=service,
                current_debt=initial_debt,
                initial_debt=initial_debt,
                principal=principal,
                total_repayment=total_repayment,
                installment_amount=installment_amount,
                installment_period=installment_period,
                provider_fee_percent=provider_fee_percent,
                provider_fee_amount=provider_fee_amount,
                user_service_permission=permission,
                account_number=account_number,
                extra_info=extra_info or {},
            )
        except IntegrityError as e:
            report_event('UserServiceIntegrityError', extras={'error': str(e)})
            raise ServiceAlreadyActivated('Service is already activated.') from e

    def fetch_and_update_debt(self):
        # TODO: implement this after third party api developed
        pass

    @classmethod
    def has_user_active_tara_service(cls, user: User):
        return cls.objects.filter(
            user=user,
            closed_at__isnull=True,
            created_at__isnull=False,
            service__provider=Service.PROVIDERS.tara,
        ).exists()


class DebtChangeLog(models.Model):
    TYPE = Choices(
        (1, 'current_debt', 'current_debt'),
        (2, 'initial_debt', 'initial_debt'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=30, decimal_places=10)
    user_service = models.ForeignKey(UserService, on_delete=models.CASCADE, related_name='debt_change_logs')
    type = models.SmallIntegerField(choices=TYPE, verbose_name='نوع بدهی')
