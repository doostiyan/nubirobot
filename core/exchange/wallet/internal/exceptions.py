class TransactionException(Exception):
    pass


class DisallowedSrcWalletType(TransactionException):
    pass


class DisallowedDstWalletType(TransactionException):
    pass


class DisallowedSystemWallet(TransactionException):
    pass


class InactiveWallet(TransactionException):
    pass


class InvalidTransactionType(TransactionException):
    pass


class InvalidTransaction(TransactionException):
    pass


class InsufficientBalance(TransactionException):
    pass


class InvalidRefModule(TransactionException):
    pass


class NonZeroAmountSum(TransactionException):
    def __init__(self, *args: object, currency: int) -> None:
        super().__init__(*args)
        self.currency = currency


class UserNotFound(Exception):
    pass
