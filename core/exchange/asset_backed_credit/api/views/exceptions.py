from dataclasses import dataclass

from rest_framework import status

from exchange.base.api import NobitexAPIError


@dataclass
class ValidationError(Exception):
    message: str


class ExternalAPIError(NobitexAPIError):
    status_code: int
    message: str
    description: str

    def __init__(self):
        super().__init__(status_code=self.status_code, message=self.message, description=self.description)


class ServiceUnavailable(ExternalAPIError):
    message = 'ServiceUnavailable'
    description = 'The service is not currently active'
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class UserServiceNotFound(ExternalAPIError):
    message = 'UserServiceUnavailable'
    description = 'Service is not active for this user'
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class APIError422(NobitexAPIError):
    def __init__(self, message: str, description: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message=message,
            description=description,
        )


class APIError402(NobitexAPIError):
    def __init__(self, message: str, description: str):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            message=message,
            description=description,
        )


class APIError501(NobitexAPIError):
    def __init__(self, message: str, description: str):
        super().__init__(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            message=message,
            description=description,
        )


class UserNotActivated(NobitexAPIError):
    def __init__(self):
        super().__init__('UserNotActivated', 'User has not activated', status_code=status.HTTP_404_NOT_FOUND)
