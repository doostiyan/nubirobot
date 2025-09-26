from collections import defaultdict
from dataclasses import asdict
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django_ratelimit.decorators import ratelimit
from pydantic import ValidationError as PydanticValidationError
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from exchange.accounts.models import User
from exchange.asset_backed_credit.api.parsers import parse_withdraw_create_request
from exchange.asset_backed_credit.api.serializers import (
    CREATE_USER_SERVICE_SERIALIZERS,
    LoanCalculationSerializer,
    serialize_service,
)
from exchange.asset_backed_credit.api.views import AmountCleaner, InternalABCView, exceptions, user_eligibility_api
from exchange.asset_backed_credit.api.views.exceptions import APIError422, ValidationError
from exchange.asset_backed_credit.currencies import ABCCurrencies
from exchange.asset_backed_credit.exceptions import (
    CloseUserServiceAlreadyRequestedError,
    ExternalProviderError,
    FeatureUnavailable,
    InsufficientBalanceError,
    InsufficientCollateralError,
    InternalAPIError,
    InvalidMarginDstWalletCurrency,
    InvalidMarginRatioAfterTransfer,
    InvalidWithdrawDestinationWallet,
    LoanCalculationError,
    MinimumInitialDebtError,
    OTPValidationError,
    PendingSettlementExists,
    PendingTransferExists,
    ServiceAlreadyActivated,
    ServiceLimitNotSet,
    ServiceMismatchError,
    ServiceNotFoundError,
    ServiceUnavailableError,
    ThirdPartyError,
    UserLimitExceededError,
    UserServiceHasActiveDebt,
    UserServiceIsNotInternallyCloseable,
    UserServicePermissionError,
    WalletValidationError,
)
from exchange.asset_backed_credit.models import (
    InternalUser,
    Service,
    SettlementTransaction,
    UserFinancialServiceLimit,
    UserService,
    UserServicePermission,
    Wallet,
)
from exchange.asset_backed_credit.services.credit.create import create_credit_service
from exchange.asset_backed_credit.services.loan.calculation import calculate_loan
from exchange.asset_backed_credit.services.loan.create import LoanCreateService
from exchange.asset_backed_credit.services.loan.debt_to_grant_ratio import get_max_available_loan
from exchange.asset_backed_credit.services.price import PricingService, get_ratios
from exchange.asset_backed_credit.services.providers.dispatcher import api_dispatcher
from exchange.asset_backed_credit.services.user_service import close_user_service, edit_user_service_debt
from exchange.asset_backed_credit.services.user_service_permission import (
    deactivate_permission,
    request_permission,
    send_permission_activation_notification,
)
from exchange.asset_backed_credit.services.wallet.transfer import create_withdraw_request
from exchange.asset_backed_credit.utils import is_user_agent_android, parse_clients_error
from exchange.base.api import NobitexAPIError, ParseError
from exchange.base.api_v2_1 import paginate
from exchange.base.decorators import measure_api_execution
from exchange.base.models import get_currency_codename
from exchange.base.parsers import parse_choices, parse_int, parse_str
from exchange.base.serializers import serialize_choices


class UserServicePermissionRequestView(InternalABCView):
    @method_decorator(measure_api_execution(api_label='abcUserServicePermissionRequest'))
    @method_decorator(ratelimit(key='user_or_ip', rate='10/h', method='POST', block=True))
    def post(self, request, service_id, *args, **kwargs):
        try:
            # send soft-update error on azki requests in old-clients
            service = Service.get_available_service(service_id)
            if service.provider == Service.PROVIDERS.azki and is_user_agent_android(
                request=request, max_version='7.0.3'
            ):
                raise NobitexAPIError(
                    message='PleaseUpdateApp',
                    description='Please Update App',
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

            request_permission(user=request.user, service_id=service_id)
        except ServiceNotFoundError as e:
            raise NobitexAPIError(message=e.message, status_code=status.HTTP_404_NOT_FOUND)
        except ServiceUnavailableError as e:
            message, description = parse_clients_error(
                request=request, message=e.__class__.__name__, description=str(e)
            )
            raise NobitexAPIError(
                message=message,
                description=description,
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except UserServicePermissionError as e:
            raise NobitexAPIError(
                message=e.message, description=e.description, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        return Response({'status': 'ok'})


class VerifyOTPView(InternalABCView):
    @method_decorator(measure_api_execution(api_label='abcUserServicePermissionActivate'))
    @method_decorator(ratelimit(key='user_or_ip', rate='10/h', method='POST', block=True))
    def post(self, request, service_id):
        """API for verifying granted permission
        Verify OTP code is sent by provider and service type

        POST /asset-backed-credit/services/<int:service_id>/activate
        """

        otp = parse_str(self.g('otp'), required=True)
        user = request.user

        try:
            service = Service.get_available_service(pk=service_id)
        except ServiceNotFoundError:
            raise NobitexAPIError(
                message='ServiceNotFoundError', description='Service not found.', status_code=status.HTTP_404_NOT_FOUND
            )
        except ServiceUnavailableError as e:
            message, description = parse_clients_error(
                request=request, message=e.__class__.__name__, description=str(e)
            )
            raise NobitexAPIError(
                message=message,
                description=description,
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # send soft-update error on azki requests in old-clients
        if service.provider == Service.PROVIDERS.azki and is_user_agent_android(request=request, max_version='7.0.3'):
            raise NobitexAPIError(
                message='PleaseUpdateApp',
                description='Please Update App',
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            user_limitation = UserFinancialServiceLimit.get_user_service_limit(user, service)
        except ServiceLimitNotSet as e:
            raise NobitexAPIError(
                message='ServiceLimit',
                description='Service Limitation does not found.',
                status_code=422,
            ) from e

        if user_limitation.max_limit == 0:
            raise NobitexAPIError(
                message='UserLimitation',
                description='You are limited to activate the service.',
                status_code=422,
            )

        granted_permission = self._get_last_inactive_permission(user=user, service=service)
        if not granted_permission:
            raise NobitexAPIError(
                message='GrantedPermissionDoseNotFound',
                description='You need to request an OTP to activate this service.',
                status_code=422,
            )

        try:
            granted_permission.verify_otp(user, service, otp)
            granted_permission.activate()
            send_permission_activation_notification(permission=granted_permission)
        except (OTPValidationError, ServiceAlreadyActivated, ServiceMismatchError) as e:
            raise NobitexAPIError(message=type(e).__name__, description=str(e), status_code=422) from e
        else:
            return self.response({'status': 'ok'})

    @staticmethod
    def _get_last_inactive_permission(user, service):
        #  a hacky way to work with old-style and new-style of requested permissions,
        #  will be removed after getting rid of old-style permissions.

        granted_permission = UserServicePermission.get_last_inactive_permission_v2(user, service)
        if not granted_permission:
            granted_permission = UserServicePermission.get_last_inactive_permission(user)

        return granted_permission


class ServiceDeactivateView(InternalABCView):
    @method_decorator(measure_api_execution(api_label='abcUserServicePermissionDeactivate'))
    @method_decorator(ratelimit(key='user_or_ip', rate='10/h', method='POST', block=True))
    def post(self, request, service_id):
        """
        API deactivate user-service-permission and close related user-services

        POST asset-backed-credit/services/<int:service_id>/deactivate
        """

        try:
            deactivate_permission(user=request.user, service_id=service_id)
        except UserServicePermissionError as e:
            raise NobitexAPIError(
                message=e.message, description=e.description, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        except ExternalProviderError as e:
            message, description = parse_clients_error(
                request=request, message=e.__class__.__name__, description=str(e)
            )
            raise APIError422(message=message, description=description)

        return self.response({'status': 'ok'})


class OptionsView(InternalABCView):
    permission_classes = ()

    @method_decorator(measure_api_execution(api_label='abcOptions'))
    @method_decorator(ratelimit(key='user_or_ip', rate='30/m', method='GET', block=True))
    def get(self, request):
        """
        This API return base information in credit such as:
        1. Currencies and active currencies: A sorted list of currencies with order
        2. Active services: the services that user can get.
        3. Ratios

        GET /asset-backed-credit/options
        """
        active_currencies = [get_currency_codename(x) for x in ABCCurrencies.get_active_currencies()]
        currencies = [get_currency_codename(x) for x in ABCCurrencies.get_all_currencies()]
        debit_active_currencies = [
            get_currency_codename(x)
            for x in ABCCurrencies.get_active_currencies(
                wallet_type=Service.get_related_wallet_type(Service.TYPES.debit)
            )
        ]
        debit_currencies = [
            get_currency_codename(x)
            for x in ABCCurrencies.get_all_currencies(wallet_type=Service.get_related_wallet_type(Service.TYPES.debit))
        ]

        if request.user.is_authenticated:
            limits = UserFinancialServiceLimit.get_user_limits_per_service(user=request.user)
        else:
            limits = UserFinancialServiceLimit.get_limits_per_service()

        grouped_service_data = defaultdict(list)
        for service in Service.get_active_services(reversed=True):
            service_type_serialized = serialize_choices(Service.TYPES, service.tp)
            grouped_service_data[service_type_serialized].append(
                serialize_service(service, opts={'limits': limits}),
            )

        return self.response(
            {
                'status': 'ok',
                'currencies': currencies,
                'activeCurrencies': active_currencies,
                'debitCurrencies': debit_currencies,
                'debitActiveCurrencies': debit_active_currencies,
                'services': grouped_service_data,
                'ratios': get_ratios(),
                'debitRatios': get_ratios(wallet_type=Wallet.WalletType.DEBIT),
            },
        )


class FinancialSummaryView(InternalABCView):
    @method_decorator(measure_api_execution(api_label='abcFinancialSummary'))
    @method_decorator(ratelimit(key='user_or_ip', rate='30/m', method='GET', block=True))
    def get(self, request):
        """
        This API provide financial summary such as:
            1.asset to debt ratio
            2.the total Rial value of all wallets
            3.the maximum credit amount that a user can obtain
            4.the total value of debts

        GET /asset-backed-credit/financial-summary
        """
        user = request.user
        pricing_service = PricingService(user=user)
        available_collateral = pricing_service.get_available_collateral()
        max_available_loan = get_max_available_loan(available_collateral)
        return self.response(
            {
                'status': 'ok',
                'assetToDebtRatio': pricing_service.get_margin_ratio(),
                'walletsRialValue': pricing_service.get_total_assets().total_nobitex_price,
                'maxAvailableCredit': available_collateral,
                'maxAvailableLoan': max_available_loan,
                'totalDebt': pricing_service.get_total_debt(),
            },
        )


class UserServicePermissionListView(InternalABCView):
    @method_decorator(measure_api_execution(api_label='abcUserServicePermissionList'))
    @method_decorator(ratelimit(key='user_or_ip', rate='30/m', method='GET', block=True))
    def get(self, request):
        """
        This API retrieve a list of user service permissions
        GET /asset-backed-credit/user-service-permissions/list
        """
        permissions = (
            UserServicePermission.objects.filter(
                user=request.user,
                created_at__isnull=False,
                revoked_at__isnull=True,
            )
            .select_related('service')
            .order_by('-created_at')
        )

        return self.response({'status': 'ok', 'permissions': permissions})


class UserServiceListView(InternalABCView):
    class Status:
        active = True
        inactive = False

    @method_decorator(measure_api_execution(api_label='abcUserServiceList'))
    @method_decorator(ratelimit(key='user_or_ip', rate='30/m', method='GET', block=True))
    def get(self, request):
        """
        This API retrieve a list of user services

        Request Parameters:
            status (Optional[str]): status of user services
            type (Optional[str]): type of <Service.TYPES> (credit/loan/...)
            provider (Optional[str]): type of <Service.PROVIDERS> (tara/...)

        GET /asset-backed-credit/user-services/list
        """
        status = parse_choices(UserServiceListView.Status, self.g('status'), required=False)
        tp = parse_choices(Service.TYPES, self.g('type'), required=False)
        provider = parse_choices(Service.PROVIDERS, self.g('provider'), required=False)

        query = Q(user=request.user)
        if status is not None:
            query &= Q(closed_at__isnull=status)
        if tp:
            query &= Q(service__tp=tp)
        if provider:
            query &= Q(service__provider=provider)

        user_services = UserService.objects.filter(query).select_related('service').order_by('-created_at')
        user_services = paginate(user_services, self)
        return self.response({'status': 'ok', 'userServices': user_services})


class CreateUserServiceView(InternalABCView):
    @method_decorator(measure_api_execution(api_label='abcUserServiceCreate'))
    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True))
    @method_decorator(user_eligibility_api)
    def post(self, request):
        """
        This API create a user services
        POST /asset-backed-credit/user-services/create
        """

        service_id = parse_int(self.g('serviceId'), required=True)
        try:
            service = Service.get_available_service(pk=service_id)
        except ServiceNotFoundError:
            raise NobitexAPIError(
                message='ServiceNotFoundError', description='Service not found.', status_code=status.HTTP_404_NOT_FOUND
            )
        except ServiceUnavailableError as e:
            message, description = parse_clients_error(
                request=request, message=e.__class__.__name__, description=str(e)
            )
            raise NobitexAPIError(
                message=message,
                description=description,
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        serializer = CREATE_USER_SERVICE_SERIALIZERS[service.tp](data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as e:
            raise NobitexAPIError(message='ParseError', status_code=status.HTTP_400_BAD_REQUEST) from e

        user = request.user
        internal_user = request.internal_user
        user_permission = UserServicePermission.get_active_permission_by_service(user=user, service=service)
        if not user_permission:
            raise NobitexAPIError(
                message='GrantedPermissionDoseNotFound',
                description='You need to grant permission to activate this service.',
                status_code=422,
            )

        amount = serializer.validated_data['amount']
        period = serializer.validated_data.get('period')
        try:
            with transaction.atomic():
                user_service = self._create_user_service(
                    user=user,
                    internal_user=internal_user,
                    service=service,
                    permission=user_permission,
                    amount=amount,
                    period=period,
                )
        except ExternalProviderError as e:
            message, description = parse_clients_error(
                request=request, message=e.__class__.__name__, description=str(e)
            )
            raise APIError422(message=message, description=description)
        except (
            ServiceLimitNotSet,
            UserLimitExceededError,
            ServiceAlreadyActivated,
            ThirdPartyError,
            MinimumInitialDebtError,
            FeatureUnavailable,
            LoanCalculationError,
            ValueError,
        ) as e:
            raise exceptions.APIError422(
                message=e.__class__.__name__,
                description=str(e),
            ) from e
        except InsufficientCollateralError as e:
            raise exceptions.APIError402(
                message=e.__class__.__name__,
                description=str(e),
            ) from e
        except NotImplementedError as e:
            raise exceptions.APIError501(
                message=e.__class__.__name__,
                description=str(e),
            ) from e

        return self.response({'status': 'ok', 'userService': user_service})

    @staticmethod
    def _create_user_service(
        user: User,
        internal_user: InternalUser,
        service: Service,
        permission: UserServicePermission,
        amount: Decimal,
        period=None,
    ):
        if service.tp == Service.TYPES.loan:
            return LoanCreateService(
                user=user,
                internal_user=internal_user,
                service=service,
                permission=permission,
                principal=amount,
                period=period,
            ).execute()

        return create_credit_service(
            user=user, internal_user=internal_user, service=service, permission=permission, amount=amount
        )


class WalletWithdrawView(InternalABCView):
    @method_decorator(measure_api_execution(api_label='abcWalletWithdrawCreate'))
    @method_decorator(ratelimit(key='user_or_ip', rate='10/h', method='POST', block=True))
    def post(self, request):
        """API for withdraw funds from collateral (credit) and debit wallet to others
        POST /asset-backed-credit/withdraws/create
        """
        try:
            data = parse_withdraw_create_request(
                request.data,
                max_len=20,
            )
        except PydanticValidationError as e:
            description = f"{e.errors()[0]['loc'][0]} {e.errors()[0]['msg']}".lower()
            raise ParseError(description)
        except WalletValidationError as e:
            raise NobitexAPIError(status_code=422, message=e.code, description=e.description) from e
        except InvalidWithdrawDestinationWallet as ex:
            raise NobitexAPIError(
                status_code=422,
                message='InvalidDstType',
                description='dstType can not be anything else that margin or spot',
            ) from ex
        except InvalidMarginDstWalletCurrency as ex:
            raise NobitexAPIError(
                status_code=422,
                message='InvalidMarginCurrency',
                description='Invalid currency selected to transfer to margin',
            ) from ex

        try:
            wallet_transfer_request = create_withdraw_request(request.user, data)
        except PendingTransferExists as ex:
            raise NobitexAPIError(
                status_code=422,
                message='PendingTransferExists',
                description='A pending transfer exists',
            ) from ex
        except PendingSettlementExists as ex:
            raise NobitexAPIError(
                status_code=422,
                message='PendingSettlementExists',
                description='A pending settlement exists, try again later.',
            ) from ex
        except (InsufficientCollateralError, InsufficientBalanceError) as ex:
            raise NobitexAPIError(
                status_code=422,
                message='InsufficientBalance',
                description=f'Active wallet balance of {get_currency_codename(ex.currency)} is less than'
                f' request amount: {ex.amount}',
            ) from ex
        except InvalidMarginRatioAfterTransfer as ex:
            raise NobitexAPIError(
                status_code=422,
                message='InvalidMarginRatioAfterTransfer',
                description='Transfers invalidates the margin ratio to below acceptable value',
            ) from ex
        except InternalAPIError as _:
            raise NobitexAPIError(
                status_code=422,
                message='WalletTransfer',
                description='Transfer service is unavailable.',
            )

        return self.response(
            {
                'status': 'ok',
                'result': wallet_transfer_request,
            },
        )


class CloseUserServiceView(InternalABCView):
    """
    POST asset-backed-credit/user-services/<int:user_service_id>/close
    """

    @method_decorator(measure_api_execution(api_label='abcUserServiceClose'))
    @method_decorator(ratelimit(key='user_or_ip', rate='5/m', method='POST', block=True))
    def post(self, request, user_service_id):
        try:
            user_service = UserService.objects.select_for_update(no_key=True).get(
                pk=user_service_id,
                user=request.user,
                closed_at__isnull=True,
            )
        except UserService.DoesNotExist as e:
            raise Http404() from e
        try:
            user_service = self._close_user_service(request, user_service)
        except (UserServiceHasActiveDebt, ThirdPartyError, PendingSettlementExists) as e:
            raise APIError422(
                message=e.__class__.__name__,
                description=str(e),
            ) from e
        except CloseUserServiceAlreadyRequestedError as e:
            message, description = parse_clients_error(
                request=request,
                message=e.__class__.__name__,
                description='قبلا درخواست لغو را ثبت کرده‌اید. در صورتی که بدهی نداشته باشید، لغو انجام می‌شود.',
            )
            raise APIError422(message=message, description=description)
        except (ExternalProviderError, UserServiceIsNotInternallyCloseable) as e:
            message, description = parse_clients_error(
                request=request, message=e.__class__.__name__, description=str(e)
            )
            raise APIError422(message=message, description=description)
        except NotImplementedError as e:
            raise exceptions.APIError501(
                message=e.__class__.__name__,
                description=str(e),
            ) from e
        return self.response({'status': 'ok', 'userService': user_service})

    def _close_user_service(self, request, user_service) -> UserService:
        self._check_pending_settlement(user_service.id)
        return close_user_service(user_service)

    @staticmethod
    def _check_pending_settlement(user_service_id):
        if SettlementTransaction.get_pending_user_settlements().filter(user_service_id=user_service_id).exists():
            raise PendingSettlementExists('A pending settlement exists, try again later.')


class TotalInstallmentsInquiryView(InternalABCView):
    @method_decorator(measure_api_execution(api_label='abcCreditTotalInstallmentsInquiry'))
    @method_decorator(ratelimit(key='user_or_ip', rate='15/m', method='GET', block=True))
    def get(self, request, user_service_id):
        try:
            user_service = UserService.objects.get(pk=user_service_id, user=request.user, closed_at__isnull=True)
        except UserService.DoesNotExist as e:
            raise Http404() from e
        try:
            amount = api_dispatcher(user_service).get_total_installments()
        except ThirdPartyError as e:
            raise APIError422(
                message=e.__class__.__name__,
                description=str(e),
            ) from e
        except NotImplementedError as e:
            raise exceptions.APIError501(
                message=e.__class__.__name__,
                description=str(e),
            ) from e
        return self.response({'status': 'ok', 'notSettled': amount})


class UserServiceDebtEditView(InternalABCView):
    @method_decorator(measure_api_execution(api_label='abcUserServiceDebtEdit'))
    @method_decorator(ratelimit(key='user_or_ip', rate='15/m', method='POST', block=True))
    def post(self, request, user_service_id):
        """
        POST /asset-backed-credit/services/<int:user_service_id>/debt/edit
        """

        try:
            new_initial_debt = AmountCleaner(self.g('newInitialDebt')).clean()
        except ValidationError as e:
            raise NobitexAPIError(
                message='ParseError',
                description=str(e),
                status_code=400,
            ) from e

        try:
            user_service = edit_user_service_debt(user_service_id, request.user, new_initial_debt)
            return self.response({'status': 'ok', 'userService': user_service})
        except UserService.DoesNotExist as e:
            raise Http404() from e
        except (
            ThirdPartyError,
            MinimumInitialDebtError,
            UserServiceHasActiveDebt,
            ServiceLimitNotSet,
            UserLimitExceededError,
            InsufficientCollateralError,
        ) as e:
            raise APIError422(
                message=e.__class__.__name__,
                description=str(e),
            ) from e
        except NotImplementedError as e:
            raise exceptions.APIError501(
                message=e.__class__.__name__,
                description=str(e),
            ) from e


class LoanCalculatorView(InternalABCView):
    permission_classes = [AllowAny]

    @method_decorator(measure_api_execution(api_label='abcLoanCalculator'))
    @method_decorator(ratelimit(key='ip', rate='20/m', method='GET', block=True))
    @method_decorator(cache_page(timeout=5 * 60, key_prefix='abc_loan_calculator'))
    def get(self, request, service_id: int):
        serializer = LoanCalculationSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        try:
            data = calculate_loan(
                service_id=service_id, principal=validated_data['principal'], period=validated_data['period']
            )
        except ServiceNotFoundError as e:
            raise NobitexAPIError(message='ServiceNotFound', description=e.message, status_code=404) from e
        except LoanCalculationError as e:
            raise NobitexAPIError(message=e.message, description=e.description, status_code=422) from e
        except NotImplementedError as e:
            raise exceptions.APIError501(
                message=e.__class__.__name__,
                description=str(e),
            )

        return self.response(data.model_dump())
