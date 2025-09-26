from typing import Optional


class CoBankException(Exception):
    code: str
    message: str

    def __init__(self, code: str, message: Optional[str] = None):
        self.code = code
        self.message = message


class ThirdPartyException(CoBankException):
    pass


class ThirdPartyAuthenticationException(ThirdPartyException):
    pass


class ThirdPartyClientUnavailable(ThirdPartyException):
    def __init__(self, code: str, message: str, status_code: int):
        super().__init__(code, message)
        self.status_code = status_code


class ThirdPartyDataParsingException(ThirdPartyException):
    def __init__(self, message: str, response: Optional[dict] = None, code: str = 'TypeError'):
        super().__init__(code, message)
        self.response = response


class ValidationException(CoBankException):
    pass


class FeatureFlagValidationException(ValidationException):
    pass


class UserLevelValidationException(ValidationException):
    pass


class BankAccountValidationException(ValidationException):
    pass


class AmountValidationException(ValidationException):
    pass


class PossibleDoubleSpendException(ValidationException):
    pass


class RefundValidationException(ValidationException):
    pass


class MultipleSourceAccountFound(CoBankException):
    pass


class MultipleBankAccountFound(CoBankException):
    pass


class NoBankAccountFound(CoBankException):
    pass


class StatementDataInvalidAmountException(CoBankException):
    pass


class InvalidTimestampException(CoBankException):
    pass
