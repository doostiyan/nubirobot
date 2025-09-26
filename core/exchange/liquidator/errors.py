class LiquidatorException(Exception):
    pass


class EmptyPrice(LiquidatorException):
    pass


class InvalidAmount(LiquidatorException):
    pass


class UnsupportedPair(LiquidatorException):
    pass


class InsufficientBalance(LiquidatorException):
    pass


class BrokerAPIError(Exception):
    pass


class BrokerAPIError4XX(Exception):
    pass


class DuplicatedOrderError(BrokerAPIError):
    pass


class SmallOrderError(BrokerAPIError4XX):
    pass


class InvalidAPIResponse(Exception):
    pass


class InvalidAPIInputError(Exception):
    pass


class MarketMakerUserNotFoundError(LiquidatorException):
    def __str__(self):
        return 'The marketmaker user does not exist'


class SettlementNotFound(Exception):
    pass


class LiquidationRequestTransactionCommitError(LiquidatorException):
    pass


class IncompatibleAmountAndPriceError(LiquidatorException):
    def __init__(self, values):
        self.values = values

    def __str__(self):
        return f'Amount and price are not compatible: {self.values}'
