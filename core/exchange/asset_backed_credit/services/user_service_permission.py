from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import (
    CloseUserServiceAlreadyRequestedError,
    NotificationProviderError,
    OTPProviderError,
    ServiceAlreadyActivated,
    ServiceAlreadyDeactivated,
    ServiceLimitNotSet,
    ThirdPartyError,
    UpdateClosedUserService,
    UserServiceHasActiveDebt,
    UserServiceIsNotInternallyCloseable,
    UserServicePermissionError,
)
from exchange.asset_backed_credit.externals.notification import notification_provider
from exchange.asset_backed_credit.externals.otp import OTPProvider
from exchange.asset_backed_credit.models import Service, UserFinancialServiceLimit, UserService, UserServicePermission
from exchange.asset_backed_credit.services.notification.user_service_activation import (
    get_service_activation_help_link_data,
)
from exchange.asset_backed_credit.services.otp import send_otp
from exchange.asset_backed_credit.services.user_service import close_user_service


def request_permission(user: User, service_id: int):
    service = Service.get_available_service(service_id)
    try:
        user_limitation = UserFinancialServiceLimit.get_user_service_limit(user, service)
    except ServiceLimitNotSet as e:
        raise UserServicePermissionError(
            message='ServiceLimit', description='Service Limitation does not found.'
        ) from e

    if user_limitation.max_limit == 0:
        raise UserServicePermissionError(
            message='UserLimitation', description='You are limited to activate the service.'
        )

    try:
        UserServicePermission.get_or_create_inactive_permission(user, service)
    except ServiceAlreadyActivated as e:
        raise UserServicePermissionError(message='ServiceAlreadyActivated', description=str(e)) from e

    try:
        send_otp(
            user=user,
            otp_type=OTPProvider.OTP_TYPES.mobile,
            usage=OTPProvider.OTP_USAGE.grant_permission_to_financial_service,
        )
    except (OTPProviderError, NotificationProviderError) as e:
        raise UserServicePermissionError(message=e.message, description=e.description) from e


def deactivate_permission(user: User, service_id: int) -> None:
    service = Service.get_active_service(service_id)
    permission = UserServicePermission.get_active_permission_by_service(user=user, service=service)
    if not permission:
        raise UserServicePermissionError(
            message='ServiceAlreadyDeactivatedError', description='Service is already deactivated.'
        )

    user_services = (
        UserService.get_actives(user=user)
        .filter(
            service=service,
            status__in=[UserService.STATUS.created, UserService.STATUS.initiated, UserService.STATUS.close_requested],
        )
        .select_for_update(no_key=True)
    )

    for user_service in user_services:
        try:
            close_user_service(user_service)
        except (
            UpdateClosedUserService,
            CloseUserServiceAlreadyRequestedError,
            UserServiceHasActiveDebt,
            ThirdPartyError,
            UserServiceIsNotInternallyCloseable,
        ) as e:
            raise UserServicePermissionError(message='ServiceDeactivationError', description=str(e))

    try:
        permission.deactivate()
        send_permission_deactivation_notification(permission=permission)
    except ServiceAlreadyDeactivated as e:
        raise UserServicePermissionError(
            message='ServiceAlreadyDeactivatedError',
            description=str(e),
        ) from e


def send_permission_activation_notification(permission: UserServicePermission):
    if not permission.created_at or permission.revoked_at:
        return

    notification_provider.send_notif(
        user=permission.user,
        message=f'سرویس {permission.service.readable_name} برای شما در نوبیتکس فعال شده است.',
    )

    if permission.user.is_email_verified:
        help_link = get_service_activation_help_link_data(permission.service)
        notification_provider.send_email(
            to_email=permission.user.email,
            template='abc/abc_service_activated',
            data={
                'financial_service': permission.service.readable_name,
                'help_link': help_link,
            },
            priority='low',
        )


def send_permission_deactivation_notification(permission: UserServicePermission):
    if not permission.created_at or not permission.revoked_at:
        return

    notification_provider.send_notif(
        user=permission.user,
        message=f'سرویس {permission.service.readable_name} غیرفعال شد.',
    )
