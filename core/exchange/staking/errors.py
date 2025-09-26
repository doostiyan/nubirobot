"""Staking (business logic related) errors"""

from django.core.exceptions import ObjectDoesNotExist, ValidationError

from exchange.base.logging import report_exception


class StakingError(Exception):
    def __init__(self, message = None) -> None:
        super().__init__(message)
        self.code = self.__class__.__name__
        self.message = message or ''


class CallSupport(StakingError):
    """For Handling Unexpected situations."""


class FailedAssetTransfer(StakingError):
    """Problem in calling `wallet` app methods"""


class InsufficientWalletBalance(StakingError):
    pass


class InvalidPlanId(StakingError, ObjectDoesNotExist):
    pass


class LowPlanCapacity(StakingError):
    pass


class InvalidAmount(StakingError, ValidationError):
    pass


class RequestAccumulationInvalidAmount(InvalidAmount):
    pass


class TooSoon(StakingError, ValidationError):
    pass


class TooLate(StakingError, ValidationError):
    pass


class AlreadyCreated(StakingError):
    pass


class AssetAlreadyStaked(StakingError):
    pass


class SystemRejectedCreateRequest(StakingError):
    pass

class UserStakingAlreadyExtended(StakingError):
    pass

class ParentIsNotCreated(StakingError, ObjectDoesNotExist):
    """Used when trying to create some plan or staking `transaction` that should have parent of
        certain type which is not being created yet.
    """


class RecentlyCanceled(StakingError):
    pass


class InvalidType(StakingError, ValidationError):
    pass


class PlanTransactionIsNotCreated(StakingError, ObjectDoesNotExist):
    pass


class NonExtendablePlan(StakingError):
    pass


class AdminMistake(StakingError):
    pass


class Restricted(StakingError):
    pass


class PlanIsNotInstantlyUnstakable(StakingError):
    pass


class CantEndReleasedStaking(StakingError):
    pass


class UserWithNegativeBalanceOrDeactivatedWallet(StakingError):
    pass


def run_safely_with_exception_report(func):
    """This decorator ensures that all
    Exceptions of the function are caught,
    ensuring that the outer scope transaction stays safe and committed.
    """

    def wrapped_transition(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            report_exception()

    return wrapped_transition


class InvalidUserPlanExtension(StakingError):
    pass


class MarkPriceNotAvailableError(StakingError):
    pass
