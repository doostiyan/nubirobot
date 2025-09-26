class TransferException(Exception):
    code: str
    message: str

    def __init__(self, code, message) -> None:
        self.code = code
        self.message = message


class InsufficientBalanceError(Exception):
    pass
