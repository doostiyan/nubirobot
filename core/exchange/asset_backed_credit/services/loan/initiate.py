from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import transaction

from exchange.accounts.models import User
from exchange.asset_backed_credit.api.serializers import InitiateLoanSchema
from exchange.asset_backed_credit.exceptions import (
    LoanCalculationError,
    LoanGetInfoError,
    ServiceAlreadyActivated,
    ThirdPartyError,
)
from exchange.asset_backed_credit.models import InternalUser, Service, UserService, UserServicePermission
from exchange.asset_backed_credit.services.loan.calculation import calculate_loan, dummy_calculate_loan
from exchange.asset_backed_credit.services.providers.dispatcher import api_dispatcher
from exchange.asset_backed_credit.services.user_service import check_margin_ratio, check_service_limit


@transaction.atomic
def initiate_loan(
    user: User,
    internal_user: InternalUser,
    service: Service,
    permission: UserServicePermission,
    init_data: InitiateLoanSchema,
) -> UserService:
    InternalUser.get_lock(user.pk)

    initial_debt, principal, period = init_data.amount, init_data.principal, init_data.period

    search_kwargs = {
        'user': user,
        'internal_user': internal_user,
        'service': service,
        'user_service_permission': permission,
        'account_number': init_data.unique_id,
    }
    user_service = _get_user_service(search_kwargs)

    validation_kwargs = {
        'initial_debt': initial_debt,
        'principal': principal,
        'installment_period': period,
    }

    if user_service is not None:
        if user_service.status != UserService.STATUS.created:
            raise ServiceAlreadyActivated('Service is already activated.')
        for key, val in validation_kwargs.items():
            if not getattr(user_service, key, None) == val:
                msg = f'Invalid value for {key}: {val}'
                raise ValueError(msg)
        _check_limit_and_margin_ratio(user=user, service=service, initial_debt=initial_debt, additional_debt=Decimal(0))

        user_service.status = UserService.STATUS.initiated
        update_fields = ['status']

        if init_data.redirect_url is not None:
            user_service.extra_info.update({'redirect_url': init_data.redirect_url})
            update_fields += ['extra_info']

        user_service.save(update_fields=update_fields)
        return user_service

    try:
        calculated_info = calculate_loan(service_id=service.id, principal=principal, period=period)
    except NotImplementedError:
        if settings.IS_TESTNET:
            calculated_info = dummy_calculate_loan(principal=principal, period=period, initial_debt=initial_debt)
        else:
            raise

    if initial_debt != Decimal(calculated_info.initial_debt_amount):
        raise LoanCalculationError(
            message='LoanCalculationError', description='Initial debt must be equal to calculated initial debt.'
        )

    _check_limit_and_margin_ratio(
        user=user, service=service, initial_debt=initial_debt, additional_debt=Decimal(initial_debt)
    )

    extra_info = calculated_info.extra_info
    if init_data.redirect_url is not None:
        extra_info.update({'redirect_url': init_data.redirect_url})

    initial_kwargs = {
        'status': UserService.STATUS.initiated,
        'current_debt': initial_debt,
        'total_repayment': initial_debt,
        'installment_amount': Decimal(calculated_info.installment_amount),
        'provider_fee_percent': Decimal(calculated_info.provider_fee_percent),
        'provider_fee_amount': Decimal(calculated_info.provider_fee_amount),
        'extra_info': extra_info,
        **search_kwargs,
        **validation_kwargs,
    }
    user_service = UserService.objects.create(**initial_kwargs)
    return user_service


def _get_user_service(search_kwargs) -> Optional[UserService]:
    try:
        return UserService.objects.get(**search_kwargs)
    except UserService.DoesNotExist:
        return None


def _check_limit_and_margin_ratio(user, service, initial_debt, additional_debt: Decimal):
    check_service_limit(user=user, service=service, amount=initial_debt)
    check_margin_ratio(user=user, amount=additional_debt, service_type=service.tp)
