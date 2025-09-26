from typing import Optional

from django.db import models
from django.db.models import Q, QuerySet, UniqueConstraint
from model_utils import Choices

from exchange.accounts.models import User, UserOTP
from exchange.asset_backed_credit.exceptions import (
    ServiceAlreadyActivated,
    ServiceAlreadyDeactivated,
    ServiceMismatchError,
    ServiceNotFoundError,
    ServiceUnavailableError,
)
from exchange.asset_backed_credit.externals.otp import OTPProvider
from exchange.asset_backed_credit.models.user import InternalUser
from exchange.asset_backed_credit.models.wallet import Wallet
from exchange.asset_backed_credit.services.otp import verify_otp
from exchange.base.calendar import ir_now
from exchange.base.logging import report_event
from exchange.base.models import Settings


class Service(models.Model):
    PROVIDERS = Choices(
        (1, 'tara', 'تارا'),
        (2, 'pnovin', 'پرداخت‌نوین'),
        (3, 'vency', 'ونسی'),
        (4, 'wepod', 'ویپاد'),
        (5, 'parsian', 'تاپ'),
        (6, 'baloan', 'بالون'),
        (7, 'maani', 'مانی'),
        (8, 'digipay', 'دیجی‌پی'),
        (9, 'azki', 'ازکی‌وام'),
        (10, 'nobifi', 'نوبیفای'),
    )
    TYPES = Choices(
        (1, 'credit', 'اعتبار'),
        (2, 'loan', 'وام'),
        (3, 'debit', 'دبیت'),
    )

    provider = models.SmallIntegerField(choices=PROVIDERS, verbose_name='سرویس دهنده')
    tp = models.SmallIntegerField(choices=TYPES, verbose_name='نوع سرویس')
    is_available = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False, verbose_name='فعال؟')
    contract_id = models.CharField(max_length=100, null=True, blank=True)
    interest = models.DecimalField(max_digits=6, decimal_places=3, default=0, verbose_name='بهره')
    fee = models.DecimalField(max_digits=6, decimal_places=3, default=0, verbose_name='کارمزد')
    options = models.JSONField(default=dict)

    class Meta:
        verbose_name = 'سرویس اعتباری'
        verbose_name_plural = 'سرویس‌های اعتباری'
        constraints = (
            UniqueConstraint(
                fields=('provider', 'tp'),
                condition=Q(is_active=True),
                name='unique_per_active_provider_tp',
            ),
        )

    def __str__(self):
        return f'سرویس {self.get_tp_display()} {self.get_provider_display()}'

    @classmethod
    def get_matching_active_service(cls, provider: int, tp: int) -> Optional['Service']:
        """
        Retrieves the first active service that matches the specified provider and provider type.

        Args:
            provider (int)
            tp (int)

        Returns:
            Service: The first active service that matches the provider ID and provider type,
                     or None if no matching service is found.
        """
        return cls.objects.filter(provider=provider, tp=tp, is_active=True).first()

    @property
    def readable_name(self) -> str:
        """
        Retrieves the readable name for the service.

        Returns:
            str: The readable name of the service, constructed from the provider and type.
        """
        return self.get_tp_display() + ' ' + self.get_provider_display()

    @classmethod
    def get_active_services(cls, ordered=True, reversed=False) -> QuerySet:
        qs = cls.objects.filter(is_active=True)
        if ordered:
            if reversed:
                return qs.order_by('-id')

            return qs.order_by('id')

        return qs

    @classmethod
    def get_active_service(cls, pk: int) -> 'Service':
        try:
            return Service.objects.get(pk=pk, is_active=True)
        except Service.DoesNotExist as e:
            raise ServiceNotFoundError(message='No Service matches the given query.') from e

    @classmethod
    def get_available_service(cls, pk: int):
        try:
            service = Service.objects.get(pk=pk, is_active=True)
        except Service.DoesNotExist as e:
            raise ServiceNotFoundError(message='No service matches the given query.') from e

        if not service.is_available:
            service_type = Service.TYPES._display_map[service.tp]
            message = f'در حال حاضر، سرویس‌دهنده ظرفیتی برای اعطای {service_type} ندارد. لطفا روزهای آینده دوباره این صفحه را بررسی کنید.'
            raise ServiceUnavailableError(message)

        return service

    @classmethod
    def get_related_wallet_type(cls, service_type: int):
        if service_type == Service.TYPES.debit and Settings.get_flag('abc_debit_wallet_enabled'):
            return Wallet.WalletType.DEBIT
        return Wallet.WalletType.COLLATERAL


class UserServicePermission(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, verbose_name='سرویس اعتباری')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='کاربر')
    internal_user = models.ForeignKey(
        InternalUser,
        on_delete=models.CASCADE,
        verbose_name='کاربر',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ ایجاد مجوز')
    revoked_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ لغو مجوز')
    user_otp = models.ForeignKey(UserOTP, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='کد تایید')

    class Meta:
        verbose_name = 'مجوز سرویس خارجی کاربر'
        verbose_name_plural = 'مجوزهای سرویس خارجی کاربر'

    @classmethod
    def active_permissions_queryset(cls, user: User, provider: int, service_type: int) -> QuerySet:
        return cls.objects.filter(
            service__provider=provider,
            service__tp=service_type,
            service__is_active=True,
            user=user,
            created_at__isnull=False,
            revoked_at__isnull=True,
        )

    @classmethod
    def get_active_permission(cls, user: User, provider: int, service_type: int) -> 'UserServicePermission':
        return cls.active_permissions_queryset(user, provider, service_type).first()

    @classmethod
    def get_active_permission_by_service(cls, user: User, service: Service) -> Optional['UserServicePermission']:
        """
        This function gets user and service and return active user service permission.
        Args:
            user (User): The user to check for permission.
            service (Service): The service to check for permission.
        Returns:
            UserServicePermission or None
        """
        return cls.objects.filter(user=user, created_at__isnull=False, revoked_at__isnull=True, service=service).first()

    @classmethod
    def has_permission(cls, user: User, provider: int, service_type: int) -> bool:
        """
        Checks if the specified user has a permission for the given provider and provider type.

        Args:
            user (User): The user to check for permission.
            provider (int): The provider enum to check.
            service_type (int): The service type to check.

        Returns:
            bool: True if the user has the permission, False otherwise.
        """
        return cls.active_permissions_queryset(user, provider, service_type).exists()

    @classmethod
    def get_last_inactive_permission(cls, user: User) -> Optional['UserServicePermission']:
        """
        Finds the last inactive granted permission that does not have created_at and revoked_at dates for the given user

        Args:
            user (User): The user for whom to find the last inactive permission.

        Returns:
            UserServicePermission
        """
        return (
            cls.objects.filter(
                user=user,
                created_at__isnull=True,
                revoked_at__isnull=True,
            )
            .select_related('service', 'user_otp')
            .order_by('id')
            .last()
        )

    @classmethod
    def get_last_inactive_permission_v2(cls, user: User, service: Service) -> Optional['UserServicePermission']:
        """
        Finds the last inactive granted permission that does not have created_at and revoked_at dates for the given user

        Args:
            user (User): The user for whom to find the last inactive permission.
            service (Service): The service for whom to find the last inactive permission.

        Returns:
            UserServicePermission
        """
        queryset = cls.objects.filter(
            user=user,
            service=service,
            created_at__isnull=True,
            revoked_at__isnull=True,
        )
        if queryset.count() > 1:
            report_event(f'abc-multiple-user-service-permission-error', extras={'user': user, 'service': service})

        return queryset.select_related('service', 'user_otp').order_by('id').last()

    def generate_user_otp(self, user: User, service: Service):
        """
        Generates a new OTP (One-Time Password) for the requested service in the user's granted permissions.

        If the requested service exists in the granted permissions and the previous OTP has expired,
        or if the requested service does not exist in the granted permissions, this function generates a new OTP.

        If the requested service is different from the previous service in the granted permissions,
        the service in the permission is updated.

        Raises an exception if the granted permission is already activated.

        Args:
            user (User): The user for whom to generate the OTP.
            service (Service): The requested service for which to generate the OTP.

        Returns:
            str: The OTP code for the granted permission.

        Raises:
            ServiceAlreadyActivated: If the granted permission is already activated.
        """
        # prevent to generate otp for activated permission
        if self.created_at:
            raise ServiceAlreadyActivated('Service is already activated.')

        update_fields = ['user_otp']
        otp = user.generate_otp(tp=User.OTP_TYPES.mobile)

        if self.is_new_service(service) and self.is_otp_valid(otp):
            OTPProvider.disable_existing_user_otps(user)
            user_otp = OTPProvider.create_new_user_otp(user)
        else:
            user_otp = OTPProvider.create_new_or_reuse_user_otp(user, otp)

        self.user_otp = user_otp

        if self.is_new_service(service):
            update_fields.append('service')
            self.service = service

        self.save(update_fields=update_fields)
        return user_otp.code

    def is_new_service(self, service):
        return self.service != service

    def is_otp_valid(self, otp):
        return self.user_otp and self.user_otp.code == otp

    @classmethod
    def create_or_update_inactive_permission(cls, user: User, service: Service) -> 'UserServicePermission':
        """
        Creates or updates an inactive granted permission for the given user and service.
        If the service is active for user, an `ServiceAlreadyActivated` is raised.

        Args:
            user (User): The user for whom to create or update the permission.
            service (Service): The service for which to create or update the permission.

        Returns:
            UserServicePermission: The created or updated inactive granted permission.

        Raises:
            ServiceAlreadyActivated: If the service is already active for user.
        """
        if cls.has_permission(provider=service.provider, service_type=service.tp, user=user):
            raise ServiceAlreadyActivated('Service is already activated.')

        internal_user = InternalUser.objects.get(uid=user.uid)

        # find existed permission granted
        permission = cls.get_last_inactive_permission(user)

        # if not exist, create new one
        if not permission:
            permission = cls.objects.create(service=service, user=user, internal_user=internal_user)

        return permission

    @classmethod
    def get_or_create_inactive_permission(cls, user, service):
        if cls.has_permission(provider=service.provider, service_type=service.tp, user=user):
            raise ServiceAlreadyActivated('Service is already activated.')

        internal_user = InternalUser.objects.get(uid=user.uid)

        permission = cls.get_last_inactive_permission_v2(user, service)
        if not permission:
            permission = cls.objects.create(service=service, user=user, internal_user=internal_user)

        return permission

    def is_active(self, check_service=True):
        result = self.created_at and not self.revoked_at
        if check_service:
            result = result and self.service.is_active
        return result

    def verify_otp(self, user: User, service: Service, otp: str) -> None:
        """
        Verify the OTP code for a specific user and service.

        Args:
            user (User): The user for whom the OTP code is being verified.
            service (Service): The service associated with the OTP code.
            otp (str): The OTP code to be validated.

        Raises:
            ServiceMismatchError: If the provided service does not match the service associated with the OTP.
            OTPValidationError: If the OTP code is invalid or does not match the expected OTP.

        Description:
            This function verifies the OTP code for a specific user and service. It performs the following steps:

            1. Checks if the provided service matches the service associated with the OTP.
               If they do not match, a InvalidService is raised, indicating that the OTP code is intended for
               a different service.

            2. Validates the OTP code to determine if it is valid and matches the expected OTP.
               If the OTP code is invalid or does not match the expected OTP,
               a OTPVerificationError is raised, indicating that the OTP code is incorrect
        """
        if not service or self.service != service:
            raise ServiceMismatchError('The selected service is not existed for verifying otp.')

        verify_otp(
            user=user,
            otp_type=OTPProvider.OTP_TYPES.mobile,
            usage=OTPProvider.OTP_USAGE.grant_permission_to_financial_service,
            otp_code=otp,
        )

    def activate(self) -> None:
        """
        Activate a permission in the permission model by adding the created_at date to the object.

        Returns:
            None

        Raises:
            ServiceAlreadyActivated: If the permission object is already activated.
        """
        if self.created_at:
            raise ServiceAlreadyActivated('Service is already activated.')
        self.created_at = ir_now()
        self.save(update_fields=['created_at'])

    def deactivate(self) -> None:
        """
        Deactivate a permission in the permission model by setting the revoked_at date to the object.

        Returns:
            None

        Raises:
            ServiceAlreadyDeactivated: If the permission object is already deactivated.
        """

        if self.revoked_at:
            raise ServiceAlreadyDeactivated('Service is already deactivated.')
        self.revoked_at = ir_now()
        self.save(update_fields=['revoked_at'])
