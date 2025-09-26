"""Liquidity Pool Exceptions"""


class LiquidityPoolException(Exception):
    pass


class HighDelegationAmountException(LiquidityPoolException):
    pass


class LowDelegationAmountException(LiquidityPoolException):
    pass


class ExceedCapacityException(LiquidityPoolException):
    pass


class InsufficientBalanceException(LiquidityPoolException):
    pass


class NoAccessException(LiquidityPoolException):
    pass


class PermissionDeniedException(LiquidityPoolException):
    pass


class InvalidDelegationAmount(LiquidityPoolException):
    pass


class ConversionOrderException(LiquidityPoolException):
    pass


class PartialConversionOrderException(LiquidityPoolException):
    pass


class NullAmountUDPExists(LiquidityPoolException):
    pass


class UnfilledCapacityAlertExist(LiquidityPoolException):
    pass


class UnfilledCapacityAlertDoesNotExist(LiquidityPoolException):
    pass


class DelegateWhenRevokeInProgressException(LiquidityPoolException):
    pass
