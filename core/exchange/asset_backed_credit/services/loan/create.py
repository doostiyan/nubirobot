import uuid
from decimal import Decimal

from django.db import transaction

from exchange.asset_backed_credit.exceptions import ExternalProviderError, ServiceAlreadyActivated
from exchange.asset_backed_credit.models import InternalUser, UserService
from exchange.asset_backed_credit.services.loan.calculation import calculate_loan
from exchange.asset_backed_credit.services.providers.dispatcher import api_dispatcher
from exchange.asset_backed_credit.services.user_service import check_margin_ratio, check_service_limit
from exchange.asset_backed_credit.types import USER_SERVICE_PROVIDER_MESSAGE_MAPPING, UserInfo, UserServiceCreateRequest, UserServiceCreateResponse


class LoanCreateService:
    MIN_PRINCIPAL_LIMIT = 50_000_000
    MAX_PRINCIPAL_LIMIT = 1_000_000_000

    def __init__(self, user, internal_user, service, permission, principal, period):
        self.user = user
        self.internal_user = internal_user
        self.service = service
        self.permission = permission
        self.principal = principal
        self.period = period

    @transaction.atomic
    def execute(self) -> UserService:
        if self._is_service_already_activated():
            raise ServiceAlreadyActivated('Service is already activated.')

        self._validate_principal()

        calculated_info = calculate_loan(service_id=self.service.id, principal=self.principal, period=self.period)

        InternalUser.get_lock(self.user.pk)
        self._check_user_service_limits(initial_debt=Decimal(calculated_info.initial_debt_amount))
        user_service = self._create_user_service(calculated_info)
        result = api_dispatcher(user_service).create_user_service(
            request_data=self._get_user_service_request(user_service)
        )
        if result.status == UserServiceCreateResponse.Status.FAILED:
            raise ExternalProviderError(USER_SERVICE_PROVIDER_MESSAGE_MAPPING[result.message])
        if result.status == UserServiceCreateResponse.Status.SUCCEEDED:
            user_service.status = UserService.Status.initiated
        user_service.account_number = result.provider_tracking_id
        user_service.extra_info.update(result.options)
        user_service.save()
        return user_service

    def _is_service_already_activated(self) -> bool:
        return UserService.objects.filter(
            user=self.user,
            service=self.service,
            user_service_permission=self.permission,
            status__in=(UserService.STATUS.created, UserService.STATUS.initiated),
        ).exists()

    def _validate_principal(self):
        min_principal_limit = self.service.options.get('min_principal_limit', self.MIN_PRINCIPAL_LIMIT)
        if self.principal < min_principal_limit:
            raise ValueError(f'Principal must be greater than or equal {min_principal_limit}.')

        max_principal_limit = self.service.options.get('max_principal_limit', self.MAX_PRINCIPAL_LIMIT)
        if self.principal > max_principal_limit:
            raise ValueError(f'Principal must be less than or equal {max_principal_limit}.')

    def _check_user_service_limits(self, initial_debt):
        check_service_limit(user=self.user, service=self.service, amount=initial_debt)
        check_margin_ratio(user=self.user, amount=initial_debt, service_type=self.service.tp)

    def _create_user_service(self, calculated_info) -> UserService:
        initial_debt = Decimal(calculated_info.initial_debt_amount)
        create_kwargs = {
            'user': self.user,
            'internal_user': self.internal_user,
            'service': self.service,
            'user_service_permission': self.permission,
            'account_number': str(uuid.uuid4()),
            'principal': self.principal,
            'installment_period': self.period,
            'status': UserService.STATUS.created,
            'initial_debt': initial_debt,
            'current_debt': initial_debt,
            'total_repayment': calculated_info.total_repayment_amount,
            'installment_amount': Decimal(calculated_info.installment_amount),
            'provider_fee_percent': Decimal(calculated_info.provider_fee_percent),
            'provider_fee_amount': Decimal(calculated_info.provider_fee_amount),
            'extra_info': calculated_info.extra_info,
        }
        return UserService(**create_kwargs)

    def _get_user_service_request(self, user_service: UserService) -> UserServiceCreateRequest:
        return UserServiceCreateRequest(
            user_info=UserInfo(
                national_code=user_service.user.national_code,
                mobile=user_service.user.mobile,
                first_name=user_service.user.first_name,
                last_name=user_service.user.last_name,
                birthday_shamsi=user_service.user.birthday_shamsi,
            ),
            amount=int(user_service.principal),
            period=int(user_service.installment_period) if user_service.installment_period is not None else None,
            unique_id=str(user_service.external_id),
            extra_info=user_service.extra_info,
        )
