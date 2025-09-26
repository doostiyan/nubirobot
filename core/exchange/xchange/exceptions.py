class XchangeError(Exception):
    def __init__(self, message, *args: object) -> None:
        self.message = message
        super().__init__(message, *args)


class InvalidPair(XchangeError):
    pass


class PairIsClosed(XchangeError):
    pass


class FailedAssetTransfer(XchangeError):
    pass


class QuoteIsNotAvailable(XchangeError):
    pass


class FailedConversion(XchangeError):
    pass


class ConversionTimeout(XchangeError):
    pass


class FailedFetchStatuses(XchangeError):
    pass


class InvalidQuoteAmount(XchangeError):
    pass


class MarketUnavailable(XchangeError):
    pass


class UserLimitationExceeded(XchangeError):
    pass


class MarketLimitationExceeded(XchangeError):
    pass


class ThereIsNoNewTradeError(XchangeError):
    pass
