from decimal import ROUND_UP, Decimal
from enum import Enum
from typing import List, Optional, Tuple, Union

from exchange.asset_backed_credit.exceptions import ThirdPartyError, UserServiceIsNotInternallyCloseable
from exchange.asset_backed_credit.externals.providers.azki import (
    AzkiCalculatorAPI,
    AzkiCreateAccountAPI,
    AzkiServiceOptionsAPI,
)
from exchange.asset_backed_credit.externals.providers.azki import CreateResponseSchema as AzkiCreateResponseSchema
from exchange.asset_backed_credit.externals.providers.digipay import DigipayCreateAccountAPI, DigipayGetAccountAPI
from exchange.asset_backed_credit.externals.providers.digipay import Status as DigipayAccountStatus
from exchange.asset_backed_credit.externals.providers.digipay.api import DigipayCloseAccountAPI, DigipayStoresAPI
from exchange.asset_backed_credit.externals.providers.parsian import (
    DebitCardOTPRequestAPI,
    DebitCardOTPVerifyAPI,
    DebitCardSuspendAPI,
    IssueChildCardAPI,
    ParsianGetRequest,
)
from exchange.asset_backed_credit.externals.providers.tara import (
    TaraChargeToAccount,
    TaraCheckUserBalance,
    TaraCreateAccount,
    TaraDischargeAccount,
    TaraTotalInstallments,
)
from exchange.asset_backed_credit.externals.providers.vency import (
    VencyCalculatorAPI,
    VencyCancelOrderAPI,
    VencyCreateAccountAPI,
    VencyGetOrderAPI,
)
from exchange.asset_backed_credit.externals.restriction import UserRestrictionsDescriptionType, UserRestrictionType
from exchange.asset_backed_credit.models import Service, UserService
from exchange.asset_backed_credit.services.debit.schema import DebitCardUserInfoSchema
from exchange.asset_backed_credit.services.providers.types import CardDetail, CardStatus, UserServiceExternalDetails
from exchange.asset_backed_credit.types import (
    LoanServiceOptions,
    ProviderBasedLoanCalculationData,
    StoreSchema,
    UserServiceCloseResponse,
    UserServiceCloseStatus,
    UserServiceCreateRequest,
    UserServiceCreateResponse,
    UserServiceProviderMessage,
    UserServiceRestriction,
)
from exchange.base.logging import report_event


class IntegrationsAPIs:

    def __init__(self, user_service: Optional[UserService] = None) -> None:
        self.user_service = user_service

    def create_user_service(self, request_data: UserServiceCreateRequest) -> UserServiceCreateResponse:
        raise NotImplementedError

    def close_user_service(self) -> UserServiceCloseResponse:
        raise NotImplementedError

    def get_details(self) -> UserServiceExternalDetails:
        raise NotImplementedError

    def get_user_service_close_status(self) -> UserServiceCloseStatus:
        raise NotImplementedError

    def get_financial_user_service_summary(self):
        raise NotImplementedError

    def get_total_installments(self) -> Decimal:
        raise NotImplementedError

    def get_available_balance(self) -> Decimal:
        raise NotImplementedError

    def get_user_restrictions(self) -> List[UserServiceRestriction]:
        raise NotImplementedError


class CreditIntegrationAPIs(IntegrationsAPIs):
    def discharge_account(self, amount: Decimal) -> None:
        raise NotImplementedError

    def charge_to_account(self, amount: Decimal) -> None:
        raise NotImplementedError


class LoanIntegrationAPIs(IntegrationsAPIs):
    def update_user_service_external_info(self) -> UserService:
        raise NotImplementedError

    def calculate(self, principal: int, period: int) -> ProviderBasedLoanCalculationData:
        raise NotImplementedError

    def get_min_debt_to_grant_ration(self):
        raise NotImplementedError

    def get_service_options(self) -> Optional[LoanServiceOptions]:
        return None


class DebitIntegrationAPIs(IntegrationsAPIs):
    def get_card(self, provider_id: str) -> CardDetail:
        raise NotImplementedError

    def issue_card(self, user_info: DebitCardUserInfoSchema) -> str:
        raise NotImplementedError

    def request_otp_code(self, pan: str) -> bool:
        raise NotImplementedError

    def verify_otp_code(self, pan: str, code: str) -> bool:
        raise NotImplementedError

    def suspend_card(self, pan: str) -> bool:
        raise NotImplementedError


class StoreAPI:
    def get_stores(self) -> List[StoreSchema]:
        return []


class TaraCreditAPIs(CreditIntegrationAPIs):
    USER_RESTRICTION_CONSIDERATIONS = 'به دلیل فعال بودن اعتبار تارا، ‌کاربر امکان ویرایش شماره موبایل را ندارد.'

    def create_user_service(self, request_data: UserServiceCreateRequest) -> UserServiceCreateResponse:
        account_number = TaraCreateAccount(user_service=self.user_service, request_data=request_data).request()
        self.charge_to_account(Decimal(request_data.amount))

        return UserServiceCreateResponse(
            status=UserServiceCreateResponse.Status.SUCCEEDED,
            provider_tracking_id=account_number,
            amount=Decimal(request_data.amount),
        )

    def close_user_service(self) -> UserServiceCloseResponse:
        self.discharge_account(amount=self.user_service.current_debt)
        return UserServiceCloseResponse(status=UserServiceCloseResponse.Status.SUCCEEDED)

    def get_user_service_close_status(self) -> UserServiceCloseStatus:
        available_balance = self.get_available_balance()
        if available_balance == self.user_service.current_debt:
            return UserServiceCloseStatus.CLOSEABLE
        return UserServiceCloseStatus.NOT_CLOSEABLE

    def get_financial_user_service_summary(self) -> Tuple[Decimal, Decimal]:
        available_balance = self.get_available_balance()
        installments = self.get_total_installments()
        if available_balance + installments != self.user_service.current_debt:
            report_event(
                'TaraIncompatibilityBalance',
                extras={'available_balance': available_balance, 'debt': installments},
            )
        return available_balance, installments

    def get_total_installments(self) -> Decimal:
        return TaraTotalInstallments(user_service=self.user_service).request()

    def get_available_balance(self) -> Decimal:
        return TaraCheckUserBalance(user_service=self.user_service).request()

    def discharge_account(self, amount: Decimal) -> None:
        TaraDischargeAccount(user_service=self.user_service, amount=abs(amount)).request()

    def charge_to_account(self, amount: Decimal) -> None:
        TaraChargeToAccount(user_service=self.user_service, amount=amount).request()

    def get_user_restrictions(self) -> List[UserServiceRestriction]:
        return [
            UserServiceRestriction(
                tp=UserRestrictionType.CHANGE_MOBILE,
                description=UserRestrictionsDescriptionType.ACTIVE_TARA_CREDIT.name,
                consideration=self.USER_RESTRICTION_CONSIDERATIONS,
            )
        ]


class DigipayCreditAPIs(CreditIntegrationAPIs, StoreAPI):
    SUCCESS_STATUS = 0
    ERROR_MESSAGE_MAP = {
        19701: UserServiceProviderMessage.BLACKLISTED,
        19702: UserServiceProviderMessage.INVALID_MOBILE_NUMBER,
        19703: UserServiceProviderMessage.INVALID_IDENTITY,
        17802: UserServiceProviderMessage.UNPROCESSABLE_REQUEST,
        5363: UserServiceProviderMessage.USER_HAS_ANOTHER_CREDIT_ERROR,
        5364: UserServiceProviderMessage.USER_HAS_IN_CLOSURE_CREDIT_ERROR,
        5366: UserServiceProviderMessage.USER_HAS_ACTIVE_CREDIT_ERROR,
        19705: UserServiceProviderMessage.ALREADY_CLOSED_CREDIT_ERROR,
        19706: UserServiceProviderMessage.INVALID_REQUEST,
    }
    CREATE_ERROR_MESSAGE_MAP = {17805: UserServiceProviderMessage.USER_HAS_DEBT_CREATE_ERROR, **ERROR_MESSAGE_MAP}
    CLOSE_ERROR_MESSAGE_MAP = {17805: UserServiceProviderMessage.USER_HAS_DEBT_CLOSE_ERROR, **ERROR_MESSAGE_MAP}

    def create_user_service(self, request_data: UserServiceCreateRequest) -> UserServiceCreateResponse:
        digipay_response = DigipayCreateAccountAPI(user_service=self.user_service, request_data=request_data).request()
        if not digipay_response.result.status == self.SUCCESS_STATUS:
            return UserServiceCreateResponse(
                status=UserServiceCreateResponse.Status.FAILED,
                message=self.CREATE_ERROR_MESSAGE_MAP.get(
                    digipay_response.result.status, UserServiceProviderMessage.FAILED
                ),
            )

        if digipay_response.status not in [DigipayAccountStatus.ACTIVATED, DigipayAccountStatus.IN_PROGRESS]:
            raise ThirdPartyError()

        if digipay_response.allocated_amount is not None:
            amount = Decimal(digipay_response.allocated_amount)
        else:
            amount = Decimal(request_data.amount)

        if digipay_response.status == DigipayAccountStatus.ACTIVATED:
            status = UserServiceCreateResponse.Status.SUCCEEDED
        else:
            status = UserServiceCreateResponse.Status.REQUESTED

        return UserServiceCreateResponse(
            status=status,
            provider_tracking_id=digipay_response.tracking_code,
            amount=amount,
        )

    def get_details(self) -> UserServiceExternalDetails:
        if not self.user_service.account_number:
            raise ValueError('account number is required for Digipay inquiry')

        digipay_response = DigipayGetAccountAPI(
            account_number=self.user_service.account_number, user_service=self.user_service
        ).request()

        if digipay_response.status == DigipayAccountStatus.ACTIVATED:
            status = UserService.STATUS.initiated
        elif digipay_response.status == DigipayAccountStatus.IN_PROGRESS:
            status = UserService.STATUS.created
        elif digipay_response.status in [DigipayAccountStatus.CLOSED, DigipayAccountStatus.FAILED]:
            status = UserService.STATUS.closed
        else:
            status = None

        return UserServiceExternalDetails(
            id=digipay_response.tracking_code, status=status, amount=digipay_response.allocated_amount
        )

    def get_user_service_close_status(self) -> UserServiceCloseStatus:
        return UserServiceCloseStatus.CLOSEABLE

    def close_user_service(self) -> UserServiceCloseResponse:
        digipay_response = DigipayCloseAccountAPI(
            account_number=self.user_service.account_number,
            user_service=self.user_service,
        ).request()

        if digipay_response.result.status == 0:
            return UserServiceCloseResponse(status=UserServiceCloseResponse.Status.REQUESTED)

        return UserServiceCloseResponse(
            status=UserServiceCloseResponse.Status.FAILED,
            message=self.CLOSE_ERROR_MESSAGE_MAP.get(digipay_response.result.status, UserServiceProviderMessage.FAILED),
        )

    def get_user_restrictions(self) -> List[UserServiceRestriction]:
        return []

    def get_stores(self) -> List[StoreSchema]:
        digipay_response = DigipayStoresAPI().request()
        if digipay_response.result.status != 0:
            raise ValueError('digipay stores API returned error')
        return digipay_response.stores


class VencyLoanAPIs(LoanIntegrationAPIs):
    class Status(str, Enum):
        IN_PROGRESS = 'IN_PROGRESS'
        REJECTED = 'REJECTED'
        EXPIRED = 'EXPIRED'
        CANCELED_BY_VENCY_ADMIN = 'CANCELED_BY_VENCY_ADMIN'
        CANCELED_BY_USER = 'CANCELED_BY_USER'
        CANCELED_BY_COLLABORATOR = 'CANCELED_BY_COLLABORATOR'  # CANCELLED BY NOBITEX
        CONTRACT_SIGNED = 'CONTRACT_SIGNED'
        VERIFIED = 'VERIFIED'
        LOAN_INSTALLMENTS_PAYMENT_IN_PROGRESS = 'LOAN_INSTALLMENTS_PAYMENT_IN_PROGRESS'
        LOAN_INSTALLMENTS_PAYMENT_COMPLETED = 'LOAN_INSTALLMENTS_PAYMENT_COMPLETED'
        LOAN_COLLATERALS_RELEASE_IN_PROGRESS = 'LOAN_COLLATERALS_RELEASE_IN_PROGRESS'
        LOAN_CLEARED = 'LOAN_CLEARED'

    CANCELABLE_STATUS_VALUES = (Status.IN_PROGRESS,)
    ALREADY_CLOSED_STATUS_VALUES = (
        Status.REJECTED,
        Status.EXPIRED,
        Status.CANCELED_BY_VENCY_ADMIN,
        Status.CANCELED_BY_USER,
        Status.CANCELED_BY_COLLABORATOR,
        Status.LOAN_CLEARED,
    )

    def create_user_service(self, request_data: UserServiceCreateRequest) -> UserServiceCreateResponse:
        vency_service = VencyCreateAccountAPI(user_service=self.user_service, request_data=request_data).request()
        return UserServiceCreateResponse(
            status=UserServiceCreateResponse.Status.REQUESTED,
            provider_tracking_id=vency_service['uniqueIdentifier'],
            options={'redirect_url': vency_service['redirectUrl']},
        )

    def update_user_service_external_info(self) -> UserService:
        data = VencyGetOrderAPI(user_service=self.user_service).request()
        self.user_service.account_number = data['orderId']
        self.user_service.extra_info.update({'redirect_url': data['redirectUrl']})
        self.user_service.save(update_fields=['account_number', 'extra_info'])
        return self.user_service

    def close_user_service(self) -> UserServiceCloseResponse:
        success = VencyCancelOrderAPI(user_service=self.user_service).request()
        if not success:
            return UserServiceCloseResponse(
                status=UserServiceCloseResponse.Status.FAILED,
                message=UserServiceProviderMessage.USER_HAS_DEBT_CLOSE_ERROR,
            )

        return UserServiceCloseResponse(status=UserServiceCloseResponse.Status.SUCCEEDED)

    def get_user_service_close_status(self) -> UserServiceCloseStatus:
        data = VencyGetOrderAPI(user_service=self.user_service).request()
        status = data['status']
        if status in self.CANCELABLE_STATUS_VALUES:
            return UserServiceCloseStatus.CLOSEABLE
        if status in self.ALREADY_CLOSED_STATUS_VALUES:
            return UserServiceCloseStatus.ALREADY_CLOSED
        return UserServiceCloseStatus.NOT_CLOSEABLE

    def calculate(self, principal: int, period: int) -> ProviderBasedLoanCalculationData:
        return VencyCalculatorAPI(principal=principal, period=period).request()

    def get_min_debt_to_grant_ration(self):
        principal = 100_000_000
        data = self.calculate(principal=principal, period=1)
        total_amount = data.total_installments_amount + data.provider_fee_amount
        return Decimal(total_amount / principal).quantize(Decimal('0.01'), rounding=ROUND_UP)

    def get_user_restrictions(self) -> List[UserServiceRestriction]:
        return []


class AzkiLoanAPIs(LoanIntegrationAPIs):
    SUCCESS_STATUS = 0
    ERROR_MESSAGE_MAP = {
        22: UserServiceProviderMessage.USER_HAS_ONGOING_REQUEST_ERROR,
        72: UserServiceProviderMessage.USER_HAS_OVERDUE_PAYMENT_ERROR,
        73: UserServiceProviderMessage.USER_HAS_OVERDUE_PAYMENT_IN_BANKING_SYSTEM_ERROR,
        74: UserServiceProviderMessage.USER_HAS_BOUNCED_CHECK_ERROR,
        76: UserServiceProviderMessage.USER_HAS_ACTIVE_LOAN_ERROR,
    }

    def create_user_service(self, request_data: UserServiceCreateRequest) -> UserServiceCreateResponse:
        azki_response: AzkiCreateResponseSchema = AzkiCreateAccountAPI(
            user_service=self.user_service, request_data=request_data
        ).request()
        if not azki_response.rs_code == self.SUCCESS_STATUS:
            return UserServiceCreateResponse(
                status=UserServiceCreateResponse.Status.FAILED,
                message=self.ERROR_MESSAGE_MAP.get(azki_response.rs_code, UserServiceProviderMessage.FAILED),
            )

        azki_service = azki_response.result
        return UserServiceCreateResponse(
            status=UserServiceCreateResponse.Status.SUCCEEDED,
            provider_tracking_id=str(azki_service.request_id),
            options={
                'request_id': azki_service.request_id,
                'credit_account_id': azki_service.credit_account_id,
                'coupon_book_id': azki_service.coupon_book_id,
            },
        )

    def calculate(self, principal: int, period: int) -> ProviderBasedLoanCalculationData:
        return AzkiCalculatorAPI(principal=principal, period=period).request()

    def get_user_restrictions(self) -> List[UserServiceRestriction]:
        return []

    def get_service_options(self) -> Optional[LoanServiceOptions]:
        azki_response = AzkiServiceOptionsAPI().request()
        return LoanServiceOptions(
            min_principal_limit=azki_response.minimum_finance,
            max_principal_limit=azki_response.maximum_finance,
            periods=azki_response.periods,
        )

    def get_user_service_close_status(self) -> UserServiceCloseStatus:
        return UserServiceCloseStatus.CLOSEABLE

    def close_user_service(self) -> UserServiceCloseResponse:
        raise UserServiceIsNotInternallyCloseable('برای لغو وام لازم است از طریق سرویس‌دهنده اقدام کنید.')


class ParsianDebitAPIs(DebitIntegrationAPIs):
    def get_card(self, provider_id: str) -> CardDetail:
        result = ParsianGetRequest(request_id=provider_id).request()
        if result.detail.status == 4:
            status = CardStatus.active
        elif result.detail.status == 14:
            status = CardStatus.issued
        else:
            status = CardStatus.inactive
        return CardDetail(status=status)

    def issue_card(self, user_info: DebitCardUserInfoSchema):
        result = IssueChildCardAPI().request(user_info)
        if result.is_success:
            return result.card_request_id
        raise ThirdPartyError(f'failed to issue card')

    def request_otp_code(self, pan: str) -> bool:
        return DebitCardOTPRequestAPI().request(pan=pan)

    def verify_otp_code(self, pan, code) -> bool:
        return DebitCardOTPVerifyAPI().request(pan=pan, code=code)

    def suspend_card(self, pan: str) -> bool:
        return DebitCardSuspendAPI().request(pan=pan)


API_DISPATCHER = {
    # CREDIT
    Service.PROVIDERS.tara: {Service.TYPES.credit: TaraCreditAPIs},
    Service.PROVIDERS.digipay: {Service.TYPES.credit: DigipayCreditAPIs},
    # LOAN
    Service.PROVIDERS.vency: {Service.TYPES.loan: VencyLoanAPIs},
    Service.PROVIDERS.azki: {Service.TYPES.loan: AzkiLoanAPIs},
    # DEBIT
    Service.PROVIDERS.parsian: {Service.TYPES.debit: ParsianDebitAPIs},
}


def api_dispatcher(user_service: UserService) -> Union[CreditIntegrationAPIs, LoanIntegrationAPIs]:
    provider = user_service.service.provider
    tp = user_service.service.tp
    if provider in API_DISPATCHER and tp in API_DISPATCHER[provider]:
        return API_DISPATCHER[provider][tp](user_service)
    raise NotImplementedError('This service not implemented yet.')


def api_dispatcher_v2(
    provider: int, service_type: int
) -> Union[CreditIntegrationAPIs, LoanIntegrationAPIs, DebitIntegrationAPIs]:
    try:
        return API_DISPATCHER[provider][service_type]()
    except KeyError:
        raise NotImplementedError('This service not implemented yet.')


STORE_DISPATCHER = {Service.PROVIDERS.digipay: DigipayCreditAPIs}


def store_dispatcher(provider: int) -> StoreAPI:
    try:
        return STORE_DISPATCHER[provider]()
    except KeyError:
        raise NotImplementedError('This service not implemented yet.')
