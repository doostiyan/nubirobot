from decimal import Decimal
from itertools import zip_longest
from typing import List, Optional, Union

from cachetools.func import ttl_cache
from django.db import transaction

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import (
    CloseUserServiceAlreadyRequestedError,
    ExternalProviderError,
    InsufficientCollateralError,
    MinimumInitialDebtError,
    UpdateClosedUserService,
    UserLimitExceededError,
    UserServiceHasActiveDebt,
)
from exchange.asset_backed_credit.externals.notification import notification_provider
from exchange.asset_backed_credit.models import (
    InternalUser,
    Service,
    SettlementTransaction,
    UserFinancialServiceLimit,
    UserService,
    UserServicePermission,
)
from exchange.asset_backed_credit.services.price import PricingService, get_ratios
from exchange.asset_backed_credit.services.providers.dispatcher import api_dispatcher
from exchange.asset_backed_credit.types import (
    USER_SERVICE_PROVIDER_MESSAGE_MAPPING,
    UserServiceCloseResponse,
    UserServiceCloseStatus,
    UserServiceProviderMessage,
)
from exchange.base.logging import report_event
from exchange.base.money import money_is_zero


def create_user_service(
    user: User,
    internal_user: InternalUser,
    service: Service,
    initial_debt: Decimal,
    permission: UserServicePermission,
    account_number: Optional[str] = '',
    principal: Decimal = None,
    total_repayment: Decimal = None,
    installment_amount: Decimal = None,
    installment_period: int = None,
    provider_fee_percent: Decimal = None,
    provider_fee_amount: int = None,
    extra_info: Optional[dict] = None,
    is_service_limit_enabled=True,
    is_margin_ratio_check_enabled=True,
) -> UserService:
    InternalUser.get_lock(user.pk)
    if is_service_limit_enabled:
        check_service_limit(user=user, service=service, amount=initial_debt)
    if is_margin_ratio_check_enabled:
        check_margin_ratio(user=user, amount=initial_debt, service_type=service.tp)
    return UserService.activate(
        user=user,
        internal_user=internal_user,
        service=service,
        initial_debt=initial_debt,
        permission=permission,
        account_number=account_number,
        principal=principal,
        total_repayment=total_repayment,
        installment_amount=installment_amount,
        installment_period=installment_period,
        provider_fee_percent=provider_fee_percent,
        provider_fee_amount=provider_fee_amount,
        extra_info=extra_info,
    )


@transaction.atomic
def edit_user_service_debt(user_service_id: int, user: User, new_initial_debt: Decimal) -> UserService:
    InternalUser.get_lock(user.pk)
    user_service: UserService = UserService.objects.select_for_update(no_key=True).get(
        pk=user_service_id, user=user, closed_at__isnull=True
    )

    if new_initial_debt == user_service.initial_debt:
        return user_service

    initial_debt_diff: Decimal = new_initial_debt - user_service.initial_debt

    check_service_limit(user=user, service=user_service.service, amount=new_initial_debt)
    check_margin_ratio(user=user, amount=initial_debt_diff, service_type=user_service.service.tp)

    if new_initial_debt > user_service.initial_debt:
        return increase_user_service_debt(user_service, initial_debt_diff)

    return decrease_user_service_debt(user_service, initial_debt_diff)


@transaction.atomic
def increase_user_service_debt(user_service: UserService, initial_debt_diff: Decimal):
    user_service.update_debt(initial_debt_diff)
    api_dispatcher(user_service).charge_to_account(user_service.current_debt)
    return user_service


@transaction.atomic
def decrease_user_service_debt(user_service: UserService, initial_debt_diff: Decimal):
    _is_decrease_eligible(user_service, initial_debt_diff)

    user_service.update_debt(initial_debt_diff)
    api_dispatcher(user_service).discharge_account(initial_debt_diff)

    if money_is_zero(user_service.current_debt):
        user_service.finalize(UserService.STATUS.closed)

    return user_service


def _is_decrease_eligible(user_service: UserService, amount: Decimal):
    """
    Checks if the amount absolute value is greater than provider available balance
    """
    available_balance = api_dispatcher(user_service).get_available_balance()
    if abs(amount) > available_balance:
        raise UserServiceHasActiveDebt()


@ttl_cache(ttl=5 * 60)
def get_user_service_debt(user_service_id: int, user: User) -> Decimal:
    user_service = UserService.objects.get(pk=user_service_id, user=user, closed_at__isnull=True)
    available_balance = api_dispatcher(user_service).get_available_balance()
    return user_service.initial_debt - available_balance


@transaction.atomic
def decrease_user_service_current_debt(user_service: UserService, amount: Decimal):
    _is_decrease_eligible(user_service, amount)

    user_service.update_current_debt(amount)
    api_dispatcher(user_service).discharge_account(amount)

    if money_is_zero(user_service.current_debt):
        user_service.finalize(UserService.STATUS.closed)

    return user_service


def check_service_limit(user: User, service: Service, amount: Decimal):
    limit = UserFinancialServiceLimit.get_user_service_limit(user=user, service=service)
    if amount < limit.min_limit:
        raise MinimumInitialDebtError(f'Amount is less than {limit.min_limit} rls')

    if amount > limit.max_limit:
        raise UserLimitExceededError('The user limit exceeded')

    _check_user_aggregate_limit(user=user, max_limit=limit.max_limit, amount=amount)


def _check_user_aggregate_limit(user: User, max_limit: int, amount: Decimal):
    user_limit = UserFinancialServiceLimit.objects.filter(tp=UserFinancialServiceLimit.TYPES.user, user=user).first()
    if user_limit:
        pricing_service = PricingService(user=user)
        total_debt = pricing_service.get_total_debt()
        max_aggregate_limit = min(user_limit.limit - total_debt, max_limit)
        if amount > max_aggregate_limit:
            raise UserLimitExceededError('The user limit exceeded')


def check_margin_ratio(user: User, amount: Decimal, service_type: int):
    wallet_type = Service.get_related_wallet_type(service_type)

    total_debt = None
    if service_type == Service.TYPES.debit:
        total_debt = UserService.get_total_active_debt(user, service_type=service_type)

    margin_ratio = PricingService(
        user=user,
        wallet_type=wallet_type,
        total_debt=total_debt,
    ).get_margin_ratio(future_service_amount=amount)

    ratio = get_ratios(wallet_type)
    collateral_ratio = ratio.get('collateral_ratio_for_lock')

    if margin_ratio < collateral_ratio:
        raise InsufficientCollateralError('Amount cannot exceed active balance')


def update_credit_user_services_status():
    user_services = UserService.objects.filter(
        service__provider=Service.PROVIDERS.digipay,
        service__tp=Service.TYPES.credit,
        status__in=(
            UserService.STATUS.created,
            UserService.STATUS.initiated,
            UserService.STATUS.close_requested,
        ),
    )

    for user_service in user_services:
        update_user_service_status(user_service)


def update_user_service_status(user_service: Union[UserService, int]):
    if not isinstance(user_service, UserService):
        user_service = UserService.objects.get(
            id=user_service,
            status__in=(
                UserService.STATUS.created,
                UserService.STATUS.initiated,
                UserService.STATUS.close_requested,
            ),
        )

    try:
        details = api_dispatcher(user_service=user_service).get_details()
    except Exception as e:
        report_event(
            'update user-service status period task error',
            extras={'exception': str(e), 'user_service': user_service.id},
        )
        return

    if details.status is None:
        return
    elif (
        user_service.status
        in (UserService.STATUS.created, UserService.STATUS.initiated, UserService.STATUS.close_requested)
        and details.status == UserService.STATUS.closed
    ):
        with transaction.atomic():
            user_service = UserService.objects.select_for_update(no_key=True).get(id=user_service.id, status=user_service.status)
            user_service.update_current_debt(-user_service.current_debt)
            user_service.finalize(UserService.STATUS.closed)
    elif user_service.status == UserService.STATUS.created and details.status == UserService.STATUS.initiated:
        _updates = {'status': details.status}
        if details.amount is not None:
            _updates['current_debt'] = details.amount
        UserService.objects.filter(id=user_service.id, status=UserService.STATUS.created).update(**_updates)


@transaction.atomic
def close_user_services(user_service_ids: List[int]):
    result = {}

    user_services = (
        UserService.objects.select_for_update(of=('self',), no_key=True)
        .select_related('user')
        .filter(id__in=set(user_service_ids))
    )

    for user_service_id, user_service in zip_longest(user_service_ids, user_services, fillvalue=None):
        if not user_service:
            result[user_service_id] = {
                'status': 'failure',
                'message': 'user service not found',
            }
            continue

        if SettlementTransaction.get_pending_user_settlements().filter(user_service_id=user_service.id).exists():
            result[user_service_id] = {
                'status': 'failure',
                'message': 'user service has pending settlements',
            }
            continue

        try:
            _ = close_user_service(user_service=user_service)
        except Exception as e:
            result[user_service_id] = {
                'status': 'failure',
                'message': str(e),
            }
            continue

        result[user_service_id] = {
            'id': user_service_id,
            'status': 'success',
            'message': 'user service closed',
        }

    return result


@transaction.atomic
def close_user_service(user_service: UserService) -> UserService:
    InternalUser.get_lock(user_service.user.pk)
    if user_service.status in (UserService.STATUS.expired, UserService.STATUS.closed):
        raise UpdateClosedUserService()

    if user_service.status == UserService.STATUS.close_requested:
        raise CloseUserServiceAlreadyRequestedError()

    status = api_dispatcher(user_service).get_user_service_close_status()
    if status == UserServiceCloseStatus.NOT_CLOSEABLE:
        raise ExternalProviderError(
            USER_SERVICE_PROVIDER_MESSAGE_MAPPING[UserServiceProviderMessage.USER_HAS_DEBT_CLOSE_ERROR]
        )

    if status == UserServiceCloseStatus.ALREADY_CLOSED:
        user_service.update_current_debt(amount=-user_service.current_debt)
        user_service.finalize(UserService.STATUS.closed)
        _send_close_notification(user_service)
        return user_service

    result = api_dispatcher(user_service).close_user_service()
    if result.status == UserServiceCloseResponse.Status.SUCCEEDED:
        user_service.update_current_debt(amount=-user_service.current_debt)
        user_service.finalize(UserService.STATUS.closed)
        _send_close_notification(user_service)
        return user_service

    if result.status == UserServiceCloseResponse.Status.REQUESTED:
        user_service.status = UserService.STATUS.close_requested
        user_service.save(update_fields=['status'])
        _send_close_notification(user_service)
        return user_service

    if result.status == UserServiceCloseResponse.Status.FAILED:
        raise ExternalProviderError(USER_SERVICE_PROVIDER_MESSAGE_MAPPING[result.message])

    raise ValueError()


def _send_close_notification(user_service: UserService) -> None:
    if user_service.status == UserService.STATUS.close_requested:
        template = 'abc/abc_user_service_close_requested'
        message = f'درخواست لغو سرویس {user_service.service.readable_name} ثبت شد.'
    elif user_service.status == UserService.STATUS.closed:
        template = 'abc/abc_user_service_closed'
        message = f'سرویس {user_service.service.readable_name} لغو شد.'
    else:
        return

    notification_provider.send_notif(user=user_service.user, message=message)
    if user_service.user.is_email_verified:
        notification_provider.send_email(
            to_email=user_service.user.email,
            template=template,
            data={
                'financial_service': user_service.service.readable_name,
            },
        )


@transaction.atomic
def force_close_user_services(user_service_ids: List[int]):
    result = {}

    user_services = (
        UserService.objects.select_for_update(of=('self',), no_key=True)
        .select_related('user')
        .filter(id__in=user_service_ids)
    )

    for user_service_id, user_service in zip_longest(user_service_ids, user_services, fillvalue=None):
        if not user_service:
            result[user_service_id] = {
                'status': 'failure',
                'message': 'user service not found',
            }
            continue

        with transaction.atomic():
            if SettlementTransaction.get_pending_user_settlements().filter(user_service_id=user_service.id).exists():
                result[user_service.id] = {
                    'status': 'failure',
                    'message': 'user service has pending settlements',
                }
                continue

            try:
                _ = force_close_user_service(user_service=user_service)
            except Exception as e:
                result[user_service.id] = {
                    'status': 'failure',
                    'message': str(e),
                }
                continue

            result[user_service.id] = {
                'id': user_service.id,
                'status': 'success',
                'message': 'user service closed by force',
            }

    return result


@transaction.atomic
def force_close_user_service(user_service: Union[int, UserService]):
    if isinstance(user_service, int):
        user_service = (
            UserService.objects.select_for_update(of=('self',), no_key=True).select_related('user').get(id=user_service)
        )

    if user_service.closed_at is not None:
        raise UpdateClosedUserService()

    user_service.update_current_debt(amount=-user_service.current_debt)
    user_service.finalize(status=UserService.STATUS.closed)
    _send_close_notification(user_service)
    return user_service
