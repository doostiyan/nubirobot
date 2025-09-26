from django.core.exceptions import ValidationError


class CreditError(Exception):
    '''Parent of all Credit Error'''
    def __init__(self, message, *args: object) -> None:
        self.message = message
        super().__init__(message, *args)


class NotEnoughCollateral(CreditError):
    '''Used when user debt is or going to be more than maximum possible value'''


class UnavailablePrice(CreditError):
    '''Asset prices which are required for computing users debt and total assets worth are not available'''


class CreditLimit(CreditError):
    pass


class InvalidAmount(CreditError, ValidationError):
    pass


class CantTransferAsset(CreditError):
    pass


class AdminMistake(CreditError):
    pass
