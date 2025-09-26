import json
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import Ratelimited, ratelimit
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from exchange.asset_backed_credit.api.authentication import DebitBasicAuthentication
from exchange.asset_backed_credit.api.parsers import parse_pan, parse_transaction_request
from exchange.asset_backed_credit.exceptions import (
    CardExpiredError,
    CardInactiveError,
    CardRestrictedError,
    CardTransactionLimitExceedError,
    InsufficientCollateralError,
    InvalidIPError,
    ServiceMismatchError,
)
from exchange.asset_backed_credit.services.debit.bank_switch import create_transaction, log
from exchange.asset_backed_credit.types import TransactionResponse, bank_switch_status_code_mapping
from exchange.base.api import ParseError, PublicAPIView, get_data
from exchange.base.decorators import measure_api_execution
from exchange.base.http import get_client_ip
from exchange.base.logging import report_exception
from exchange.base.parsers import parse_str


def log_api(func):
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        client_ip, data, pan = _parse_request(request)
        response = func(request, *args, **kwargs)
        _try_log(client_ip, data, pan, request, response)
        return response

    def _parse_request(request):
        data, _ = get_data(request)
        if data is None:
            raise ParseError('request body is missing')
        pan = parse_str(data.get('PAN'), required=False)
        client_ip = get_client_ip(request)
        return client_ip, data, pan

    def _try_log(client_ip, data, pan, request, response):
        if response.status_code == status.HTTP_404_NOT_FOUND:
            return response

        response_data = json.loads(response.content) if response.content else None
        log(client_ip, request.path, pan, data, response_data, response.status_code)

    return wrapper


def exception_handler(exc, context):
    if not settings.IS_PROD:
        report_exception()

    if isinstance(exc, (NotAuthenticated, AuthenticationFailed, InvalidIPError, ServiceMismatchError)):
        return Response(status=status.HTTP_404_NOT_FOUND)

    if isinstance(exc, InsufficientCollateralError):
        return PublicAPIView.response(TransactionResponse(status=bank_switch_status_code_mapping['BALANCE_NOT_ENOUGH']))

    if isinstance(exc, CardRestrictedError):
        return PublicAPIView.response(TransactionResponse(status=bank_switch_status_code_mapping['CARD_RESTRICTED']))

    if isinstance(exc, CardExpiredError):
        return PublicAPIView.response(TransactionResponse(status=bank_switch_status_code_mapping['CARD_EXPIRED']))

    if isinstance(exc, CardInactiveError):
        return PublicAPIView.response(TransactionResponse(status=bank_switch_status_code_mapping['CARD_INACTIVE']))

    if isinstance(exc, CardTransactionLimitExceedError):
        return PublicAPIView.response(
            TransactionResponse(status=bank_switch_status_code_mapping['AMOUNT_LIMIT_EXCEEDED'])
        )

    return PublicAPIView.response(
        TransactionResponse(status=bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION'])
    )


def user_pan_custom_key(_, request):
    return parse_pan(request)


@method_decorator(log_api, name='dispatch')
class TransactionView(PublicAPIView):
    authentication_classes = [DebitBasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get_exception_handler(self):
        return exception_handler

    def handle_exception(self, exc):
        if isinstance(exc, Ratelimited):
            return JsonResponse(
                {'status': 'failed', 'message': 'Too many requests', 'code': 'TooManyRequests'}, status=429
            )
        return super().handle_exception(exc)

    @method_decorator(measure_api_execution(api_label='abcBankSwitchTransaction'))
    @method_decorator(ratelimit(key='user_or_ip', rate='1000/m', method='POST', block=True))
    @method_decorator(ratelimit(key=user_pan_custom_key, rate='5/m', method='POST', block=True))
    def post(self, request):
        transaction_request = parse_transaction_request(request)
        transaction_response = create_transaction(transaction_request, get_client_ip(request))
        return self.response(transaction_response)
