from typing import TYPE_CHECKING, Union

from django.utils.decorators import method_decorator
from pydantic import ValidationError
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.api.serializers import (
    INITIATE_USER_SERVICE_SCHEMA_MAP,
    InitiateCreditSchema,
    InitiateLoanSchema,
)
from exchange.asset_backed_credit.api.views import AssetBackedCreditAPIView
from exchange.asset_backed_credit.api.views.exceptions import APIError422, ServiceUnavailable
from exchange.asset_backed_credit.exceptions import (
    AmountIsLargerThanDebtOnUpdateUserService,
    FeatureUnavailable,
    InsufficientCollateralError,
    LoanCalculationError,
    LoanGetInfoError,
    MinimumInitialDebtError,
    ServiceAlreadyActivated,
    ServiceLimitNotSet,
    SettlementError,
    UserLimitExceededError,
)
from exchange.asset_backed_credit.models import (
    InternalUser,
    Service,
    SettlementTransaction,
    UserFinancialServiceLimit,
    UserService,
    UserServicePermission,
)
from exchange.asset_backed_credit.services.loan.initiate import initiate_loan
from exchange.asset_backed_credit.services.price import PricingService
from exchange.asset_backed_credit.services.user_service import create_user_service
from exchange.base.api import NobitexAPIError
from exchange.base.decorators import measure_api_execution

if TYPE_CHECKING:
    from decimal import Decimal


class EstimationView(AssetBackedCreditAPIView):
    parameters = ('nationalCode', 'serviceType')

    @method_decorator(measure_api_execution(api_label='abcExternalEstimate'))
    def post(self, request):
        try:
            user_limit = UserFinancialServiceLimit.get_user_service_limit(self.user, self.service)
        except ServiceLimitNotSet as e:
            raise ServiceUnavailable() from e

        min_credit = min([user_limit.max_limit, PricingService(self.user).get_available_collateral()])
        total_debt = UserService.get_total_active_debt(
            user=self.user, service_provider=self.service.provider, service_type=self.service.tp
        )

        return self.response(
            {'status': 'ok', 'amount': str(round(min_credit)), 'total_debt': str(int(total_debt))},
        )


class LockView(AssetBackedCreditAPIView):
    parameters = ('nationalCode', 'serviceType', 'trackId', 'amount')

    @method_decorator(measure_api_execution(api_label='abcExternalLock'))
    def post(self, request):
        data = request.data
        try:
            init_data = INITIATE_USER_SERVICE_SCHEMA_MAP[self.service.tp](**data)
        except ValidationError as e:
            raise NobitexAPIError(message='ParseError', status_code=status.HTTP_400_BAD_REQUEST)
        try:
            self.user_service = self._create_user_service(
                user=self.user,
                internal_user=self.internal_user,
                service=self.service,
                permission=self.permission,
                init_data=init_data,
            )
        except InsufficientCollateralError as e:
            raise NobitexAPIError(
                message='InsufficientBalance',
                description='Amount cannot exceed active balance',
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
            ) from e
        except ServiceLimitNotSet as e:
            raise ServiceUnavailable() from e
        except UserLimitExceededError as e:
            raise NobitexAPIError(
                message='LimitExceededError',
                description='The user limit exceeded',
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            ) from e
        except (
            ServiceAlreadyActivated,
            FeatureUnavailable,
            LoanCalculationError,
            LoanGetInfoError,
            NotImplementedError,
        ) as e:
            raise NobitexAPIError(
                message=e.__class__.__name__,
                description=str(e),
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            ) from e
        except MinimumInitialDebtError as e:
            raise APIError422(
                message=e.__class__.__name__,
                description=str(e),
            ) from e

        return self.response(
            {
                'status': 'ok',
            }
        )

    def _create_user_service(
        self,
        user: User,
        internal_user: InternalUser,
        service: Service,
        permission: UserServicePermission,
        init_data: Union[InitiateCreditSchema, InitiateLoanSchema],
    ):
        if service.tp == Service.TYPES.loan:
            return initiate_loan(
                user=user,
                internal_user=internal_user,
                service=service,
                permission=permission,
                init_data=init_data,
            )

        return create_user_service(
            user=self.user,
            internal_user=internal_user,
            service=service,
            initial_debt=init_data.amount,
            permission=self.permission,
        )


class UnlockView(AssetBackedCreditAPIView):
    parameters = ('nationalCode', 'serviceType', 'trackId', 'amount')

    @method_decorator(measure_api_execution(api_label='abcExternalUnlock'))
    def post(self, request):
        amount: Decimal = self.cleaned_data['amount']
        user_service = self.identify_user_service()

        if SettlementTransaction.get_pending_user_settlements().filter(user_service_id=user_service.id).exists():
            raise NobitexAPIError(
                message='SettlementError',
                description='Settlement process is running!',
                status_code=status.HTTP_423_LOCKED,
            )
        try:
            user_service.update_current_debt(-amount)
            user_service.finalize(UserService.STATUS.settled)
        except AmountIsLargerThanDebtOnUpdateUserService as e:
            raise NobitexAPIError(
                message='InappropriateAmount',
                description='Requested unblock amount exceeds user balance.',
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            ) from e

        return self.response(
            {
                'status': 'ok',
            },
        )


class SettlementView(AssetBackedCreditAPIView):
    parameters = ('nationalCode', 'serviceType', 'trackId', 'amount')

    @method_decorator(measure_api_execution(api_label='abcExternalSettle'))
    def post(self, request):
        amount: Decimal = self.cleaned_data['amount']
        if amount >= 1_000_000_000_0:
            raise NobitexAPIError(
                message='ValidationError',
                description='Amount too large, amount should be lower than 1B Toman/10B Rial.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        user_service = self.identify_user_service()
        try:
            SettlementTransaction.create(user_service=user_service, amount=amount)
        except AmountIsLargerThanDebtOnUpdateUserService as e:
            raise NobitexAPIError(
                message='InappropriateAmount',
                description='Requested settlement amount exceeds user active debt.',
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            ) from e
        except SettlementError as e:
            raise NobitexAPIError(
                message='SettlementError',
                description='Another settlement process is running!',
                status_code=status.HTTP_423_LOCKED,
            ) from e

        return self.response({'status': 'ok'})
