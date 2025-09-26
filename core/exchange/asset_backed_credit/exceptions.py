from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from rest_framework import status

from exchange.base.api import NobitexAPIError


class ServiceLimitNotSet(Exception):
    pass


class ServicePermissionNotFound(Exception):
    pass


class ServiceAlreadyActivated(Exception):
    pass


class ServiceAlreadyDeactivated(Exception):
    pass


class ServiceMismatchError(Exception):
    pass


class OTPValidationError(Exception):
    pass


class InvalidIPError(Exception):
    pass


class MissingSignatureError(Exception):
    pass


class InvalidSignatureError(Exception):
    pass


class LiquidationOrderAlreadyCreated(Exception):
    pass


class CreateLiquidationOrderError(Exception):
    pass


class LiquidationAlreadyClosed(Exception):
    pass


class LiquidationAmountGreaterThanDebt(Exception):
    pass


class CannotEstimateSrcAmount(Exception):
    pass


class ClientError(Exception):
    pass


class ThirdPartyError(Exception):
    pass


class InternalAPIError(Exception):
    pass


class DuplicateRequestError(Exception):
    pass


@dataclass
class InsufficientCollateralError(Exception):
    currency: Optional[int] = None
    amount: Optional[Decimal] = None


@dataclass
class InsufficientBalanceError(Exception):
    currency: Optional[int] = None
    amount: Optional[Decimal] = None


class SettlementNeedsLiquidation(Exception):
    pass


class UnexpectedSettlementLowLiquidity(Exception):
    pass


class UserHasBalanceWhenInsuranceRequested(Exception):
    pass


class InsuranceFundAccountLowBalance(Exception):
    pass


class UpdateClosedUserService(Exception):
    pass


class UserLimitExceededError(Exception):
    pass


class AmountIsLargerThanDebtOnUpdateUserService(Exception):
    pass


class SettlementError(Exception):
    pass


class PendingTransferExists(Exception):
    pass


class PendingSettlementExists(Exception):
    pass


class InvalidWithdrawDestinationWallet(Exception):
    pass


class InvalidMarginDstWalletCurrency(Exception):
    pass


class InvalidMarginRatioAfterTransfer(Exception):
    pass


class MinimumInitialDebtError(Exception):
    pass


class UserServiceHasActiveDebt(Exception):
    pass


class CreateAPILogError(Exception):
    pass


class InvalidAmountError(Exception):
    pass


class InvalidProviderError(Exception):
    pass


class InvalidMTIError(Exception):
    pass


class UserServiceNotFoundError(Exception):
    pass


class ProviderError(Exception):
    def __init__(self, message, description):
        self.message = message
        self.description = description


class OTPProviderError(ProviderError):
    pass


class NotificationProviderError(ProviderError):
    pass


class UserServicePermissionError(Exception):
    def __init__(self, message, description=None):
        self.message = message
        self.description = description


class ServiceNotFoundError(Exception):
    def __init__(self, message):
        self.message = message


class LoanCalculationError(Exception):
    def __init__(self, message, description=None):
        self.message = message
        self.description = description


class LoanGetInfoError(Exception):
    def __init__(self, message, description=None):
        self.message = message
        self.description = description


class UserLevelRestrictionError(Exception):
    def __init__(self, message, description=None):
        self.message = message
        self.description = description


class UserNotFoundError(Exception):
    pass


class FeatureUnavailable(Exception):
    pass


class ReconAlreadyProcessedError(Exception):
    pass


class SettlementReconError(Exception):
    pass


class SettlementReverseError(Exception):
    pass


class PriceNotAvailableError(Exception):
    pass


class CardNotFoundError(Exception):
    pass


class CardRestrictedError(Exception):
    pass


class CardExpiredError(Exception):
    pass


class CardInactiveError(Exception):
    pass


class CardAlreadyExists(Exception):
    pass


class CardInvalidStatusError(Exception):
    pass


class DuplicateDebitCardRequestByUser(Exception):
    pass


class OTPServiceUnavailable(Exception):
    pass


class CardTransactionLimitExceedError(Exception):
    pass


class CardUnknownLevelError(Exception):
    pass


class ServiceUnavailableError(Exception):
    pass


class WalletInvalidSrcError(Exception):
    pass


class DepositAPIError(NobitexAPIError):
    def __init__(self, code, description=None, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY):
        super().__init__(message=code, description=description, status_code=status_code)


class WalletValidationError(Exception):
    def __init__(self, code, description=None):
        self.code = code
        self.description = description


class WalletInvalidDstError(Exception):
    pass


class TransactionError(Exception):
    pass


class TransactionInvalidError(TransactionError):
    pass


class TransactionInsufficientBalanceError(TransactionError):
    pass


class TransactionWalletInactiveError(TransactionError):
    pass


class TransactionListEmptyError(TransactionError):
    pass


class TransactionListMaxSizeError(TransactionError):
    pass


class TransactionNonZeroAmountSumError(TransactionError):
    def __init__(self, *args: object, currency: int) -> None:
        super().__init__(*args)
        self.currency = currency


class DebitCardCreationServiceTemporaryUnavailable(Exception):
    pass


class DebitCardTransactionServiceTemporaryUnavailable(Exception):
    pass


class ExternalProviderError(Exception):
    pass


class UserServiceIsNotInternallyCloseable(Exception):
    pass


class CloseUserServiceAlreadyRequestedError(Exception):
    pass


class TransferCurrencyRequiredError(Exception):
    pass
