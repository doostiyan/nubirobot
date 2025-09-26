from django.contrib.auth.models import User
from rest_framework import status

from exchange.base.api import NobitexAPIError
from exchange.base.logging import report_event
from exchange.marketing.exceptions import (
    InvalidCampaignException,
    MissionHasNotBeenCompleted,
    NoDiscountCodeIsAvailable,
)
from exchange.promotions.exceptions import (
    ActiveUserDiscountExist,
    CreateNewUserDiscountBudgetLimit,
    DiscountDoesNotExist,
    NotActiveDiscount,
    UserRestrictionError,
    WebEngageUserIdDoesNotExist,
)
from exchange.web_engage.exceptions import (
    ESPSendMessageException,
    InvalidPhoneNumber,
    RecipientBlackListed,
    UnsupportedRequestVersion,
)
from exchange.web_engage.models.email_log import WebEngageEmailLog
from exchange.web_engage.types import ESPDeliveryStatusCode, SSPDeliveryStatusCode


class WebEngageError(NobitexAPIError):
    code: str
    description: str
    supported_version: str
    status_code: int
    error_status_code: int

    def __init__(self, code=None, description=None, supported_version=None, error_status_code=None, status_code=None):
        super().__init__(
            status_code=status_code or self.status_code,
            message=code or self.code,
            description=description or self.description,
        )

        self.error_status_code = error_status_code
        self.supported_version = supported_version


class MalformedTokenHeader(WebEngageError):
    code = 'AuthenticationError'
    description = 'Malformed authentication header.'
    status_code = status.HTTP_401_UNAUTHORIZED

    def __init__(self, error_status_code=None):
        super().__init__()
        self.error_status_code = error_status_code


class WrongToken(WebEngageError):
    code = 'AuthenticationError'
    description = 'Wrong Token.'
    status_code = status.HTTP_401_UNAUTHORIZED

    def __init__(self, error_status_code=None):
        super().__init__()
        self.error_status_code = error_status_code


def esp_delivery_exception_mapper(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except WebEngageEmailLog.DoesNotExist:
            report_event('ESP webhook error: email request not found')
            raise WebEngageError(code='ERROR', status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            report_event(f'ESP webhook has error: {str(e)}')
            raise WebEngageError(code='ERROR', status_code=status.HTTP_400_BAD_REQUEST)

    return wrapper


def esp_exception_mapper(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except UnsupportedRequestVersion:
            raise WebEngageError(
                code='ERROR',
                error_status_code=ESPDeliveryStatusCode.UNSUPPORTED_OR_UNKNOWN_VERSION.value,
                description='Unsupported version',
                supported_version="1.0",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except ESPSendMessageException as e:
            raise WebEngageError(
                code='ERROR',
                error_status_code=e.status_code,
                description=e.status_code_message,
                status_code=e.http_status_code,
            )
        except WebEngageEmailLog.DoesNotExist:
            report_event(f'ESP webhook error: email request not found')
            raise WebEngageError(code='ERROR', status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            report_event(f'ESP webhook has error: {str(e)}')
            raise WebEngageError(code='ERROR', status_code=status.HTTP_400_BAD_REQUEST)
        except:
            raise WebEngageError(
                code='ERROR',
                error_status_code=ESPDeliveryStatusCode.UNKNOWN_REASON.value,
                description='Unknown error occurred',
                status_code=status.HTTP_200_OK,
            )

    return wrapper


def ssp_exception_mapper(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except UnsupportedRequestVersion:
            raise WebEngageError(
                code='sms_rejected',
                error_status_code=SSPDeliveryStatusCode.UNSUPPORTED_PAYLOAD_VERSION.value,
                description='Version not supported',
                supported_version="2.0",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except InvalidPhoneNumber:
            raise WebEngageError(
                code='sms_rejected',
                error_status_code=SSPDeliveryStatusCode.INVALID_MOBILE_NUMBER.value,
                description='Invalid mobile number',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except RecipientBlackListed:
            raise WebEngageError(
                code='sms_rejected',
                error_status_code=SSPDeliveryStatusCode.RECIPIENT_BLACKLISTED.value,
                description='Recipient black listed',
                status_code=status.HTTP_403_FORBIDDEN,
            )
        except:
            raise WebEngageError(
                code='sms_rejected',
                error_status_code=SSPDeliveryStatusCode.UNKNOWN_REASON.value,
                description='Unknown error occurred',
                status_code=status.HTTP_200_OK,
            )

    return wrapper


def discount_exception_mapper(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except WebEngageUserIdDoesNotExist:
            raise NobitexAPIError(
                message='WebengageIdError',
                description='Webengage user_id does not exist.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except DiscountDoesNotExist:
            raise NobitexAPIError(
                message='WebengageIdError',
                description='Webengage discount_id does not exist.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except UserRestrictionError:
            raise NobitexAPIError(
                message='UserRestrictionError',
                description='Cannot create new discount for limited user.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except ActiveUserDiscountExist:
            raise NobitexAPIError(
                message='ActiveDiscountExistError',
                description='Active user discount is existed.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except CreateNewUserDiscountBudgetLimit:
            raise NobitexAPIError(
                message='DiscountBudgetLimit',
                description='Discount budget limit.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except NotActiveDiscount:
            raise NobitexAPIError(
                message='NotActiveDiscount',
                description='Discount is not active.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except InvalidCampaignException as e:
            raise NobitexAPIError(
                message='InvalidCampaign',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except NoDiscountCodeIsAvailable as e:
            raise NobitexAPIError(
                message='NoDiscountCodeIsAvailable',
                description='not found any available discount to assign the user',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except MissionHasNotBeenCompleted as e:
            raise NobitexAPIError(
                message='MissionHasNotBeenCompleted',
                description='mission has not been completed yet',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except User.DoesNotExist as e:
            raise NobitexAPIError(
                message='UserDoesNotExist',
                description='user does not exist with requested identifier',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    return wrapper
