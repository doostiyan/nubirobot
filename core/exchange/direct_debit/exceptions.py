from exchange.base.api import NobitexAPIError
from exchange.direct_debit.integrations.faraboom_errors import FARABOOM_ERRORS_FOR_CLIENTS


# create
class ThirdPartyAuthenticatorError(Exception):
    pass


class ThirdPartyUnavailableError(Exception):
    pass


class ThirdPartyClientError(Exception):
    """
    A general error raised when we are trying to request third party , and we couldn't identify the error
    """
    pass


class ThirdPartyConnectionError(Exception):
    pass


class ThirdPartyError(Exception):
    def __init__(self, code: str):
        if code in FARABOOM_ERRORS_FOR_CLIENTS:
            error_info = FARABOOM_ERRORS_FOR_CLIENTS.get(code, {})
            self.message = error_info.get('code')
            self.description = error_info.get('message')
        else:
            self.message = 'ThirdPartyError'
            self.description = 'Third party error. please try again later'

    def convert_to_api_error(self, status_code: int = 400) -> NobitexAPIError:
        return NobitexAPIError(status_code=status_code, message=self.message, description=self.description)


class DirectDepositError(Exception):
    pass


class MaxDailyAmountExceededError(DirectDepositError):
    pass


class MaxDailyCountExceededError(DirectDepositError):
    pass


class MaxAmountExceededError(DirectDepositError):
    pass


class MaxAmountBankExceededError(DirectDepositError):
    pass


class MinAmountNotMetError(DirectDepositError):
    pass


class DirectDebitBankNotFoundError(Exception):
    pass


class DirectDebitBankNotActiveError(Exception):
    pass


class ContractStartDateError(Exception):
    pass


class ContractStatusError(Exception):
    pass


class StatusUnchangedError(Exception):
    pass


class MaxTransactionAmountError(Exception):
    pass


class DailyMaxTransactionCountError(Exception):
    pass


class ContractEndDateError(Exception):
    pass


class ContractIntegrityError(Exception):
    pass


class ContractCanNotBeCanceledAtProviderError(Exception):
    pass


class DiffResolverError(Exception):
    pass
