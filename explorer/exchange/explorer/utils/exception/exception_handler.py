from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError

from rest_framework.response import Response
from rest_framework.exceptions import APIException

from requests.exceptions import ProxyError, SSLError
from exchange.blockchain.utils import (AddressNotExist, APIError, APIKeyMissing, BadGateway, NetworkNotExist,
                                       GatewayTimeOut, InternalServerError, RateLimitError, PaymentRequired, Forbidden,
                                       ValidationError as BlockchainValidationError)

from ..dto import DTO
from ..logging import get_logger
from .custom_exceptions import CustomException
from exchange.explorer.utils.prometheus import exceptions_counter, get_request_info


@dataclass
class ErrorDTO(DTO):
    code: int
    message_code: str
    detail: str


external_api_exceptions = {
    RateLimitError: 'rate limit error',
    InternalServerError: 'internal server error',
    BadGateway: 'bad gateway',
    GatewayTimeOut: 'gateway timeout',
    APIKeyMissing: 'api key missing',
    Forbidden: 'forbidden',
    PaymentRequired: 'payment required',
    SSLError: 'ssl error',
    ProxyError: 'proxy error'
}


def exception_handler(exc, context):
    logger = get_logger()
    logger.exception(exc)

    code = 500
    message_code = 'internal_server_error'
    detail = ''

    if isinstance(exc, APIException):
        code = exc.status_code
        message_code = exc.default_code
        detail = exc.detail

    elif isinstance(exc, CustomException):
        code = exc.code
        message_code = exc.message_code
        detail = exc.detail

    elif isinstance(exc, DjangoValidationError):
        code = 400
        message_code = 'invalid'
        if isinstance(exc, DjangoValidationError):
            if hasattr(exc, "message_dict"):
                detail = exc.message_dict
            elif hasattr(exc, "message"):
                detail = exc.message
            elif hasattr(exc, "messages"):
                detail = exc.messages

    elif isinstance(exc, ObjectDoesNotExist):
        code = 404
        message_code = 'object_does_not_exist'
        detail = exc.args[0] if exc.args else ''

    elif isinstance(exc, tuple(external_api_exceptions.keys())):
        code = 500
        message_code = 'internal_server_error'
        detail = 'External api error:' + external_api_exceptions[exc.__class__]

    elif isinstance(exc, APIError):
        detail = exc.args[0] if exc.args else ''
        if any(item in detail for item in ('404', 'valid', 'invalid', 'found')):
            code = 404
            message_code = 'not_found'

    elif isinstance(exc, (AddressNotExist, NetworkNotExist, BlockchainValidationError)):
        code = 404
        message_code = 'not_found'
        detail = exc.args[0] if exc.args else ''

    else:
        detail = str(exc.args[0]) if exc.args else getattr(exc, 'detail', '') if settings.DEBUG else ''

    response = ErrorDTO(code=code, message_code=message_code, detail=detail).get_data()

    request = context['request']
    labels = get_request_info(request)
    exceptions_counter.labels(**labels, type=message_code).inc()

    return Response(response, status=response['code'])
