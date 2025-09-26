"""API Utilities v2.1

usage:

@api(GET='20/1m', POST='5/2m')
def example_view(request):
    if request.method == 'POST':
        return Example.objects.create(
            foo=parse_int(request.g('foo')),
            bar=request.g('bar', 'sampleBar'),
        )
    return Example.objects.all()
"""

__all__ = ['NobitexError', 'public_api', 'api', 'InternalAPIView']

from functools import wraps
from typing import Iterable

from django.db import transaction
from django.db.models import QuerySet
from django.http import Http404
from django.http.response import HttpResponseNotAllowed, JsonResponse
from django_ratelimit.decorators import is_ratelimited
from django_ratelimit.exceptions import Ratelimited
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView as RestAPIView

from exchange.base.api import APIMixin, get_data
from exchange.base.api import handle_exception as handle_exception_v1
from exchange.base.api import handle_ratelimit, is_nobitex_server_ip
from exchange.base.api import run_api_view as run_raw_api_view
from exchange.base.api_logger import log_api
from exchange.base.api_v2 import run_api_view_in_atomic_transaction
from exchange.base.http import get_client_ip
from exchange.base.internal.authentications import InternalAuthentication
from exchange.base.internal.idempotency import idempotent
from exchange.base.internal.permissions import AllowedServices
from exchange.base.internal.services import Services
from exchange.base.parsers import parse_int
from exchange.base.serializers import serialize


class NobitexError(Exception):
    def __init__(self, *, code, message=None, status_code=None):
        super().__init__(code, message)
        self.status_code = status_code
        self.code = code
        self.message = message


def handle_exception(e):
    if isinstance(e, NobitexError):
        return JsonResponse(status=e.status_code or 400, data={
            'status': 'failed',
            'code': e.code,
            'message': e.message or e.code,
        })
    return handle_exception_v1(e)


def paginate(data, request):
    page = parse_int(request.g('page') or 1)
    page_size = parse_int(request.g('pageSize') or 50)
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 50
    if page_size > 100:
        page_size = 100
    paged_data = list(data[(page - 1) * page_size:page * page_size + 1])
    if len(paged_data) > page_size:
        paged_data.pop()
        has_next = True
    else:
        has_next = False
    return {
        'result': paged_data,
        'hasNext': has_next,
    }


def run_api_view(view, request, atomic=True, *args, **kwargs):
    # Parse request data
    data, request.uploaded_files = get_data(request)
    if isinstance(data, str) and data == '':
        data = {}
    if data is None:
        data = {}

    def g(k, default=None):
        return data.get(k, default)

    request.g = g

    # Run and track exceptions
    try:
        if atomic:
            with transaction.atomic():
                r = view(request, *args, **kwargs)
        else:
            r = view(request, *args, **kwargs)

    except Exception as e:
        return handle_exception(e)
    if isinstance(r, JsonResponse):
        return r
    return JsonResponse(
        {
            'status': 'ok',
            **serialize(
                paginate(r, request) if isinstance(r, (tuple, list, QuerySet)) else {'result': r},
                convert_to_camelcase=True,
            ),
        },
        safe=False,
    )


def translate_rate_limit_to_message(rate, opts=None):
    """This method serialize rate limit values such as:
        - '10/5s'
        - '100/h'
        - '50/1m'
        To human readable values:
         - 'لطفا 5 ثانیه صبر نمایید'
         - 'لطفا 1 ساعت صبر نمایید'
         - 'لطفا 1 دقیقه صبر نمایید'
        So it could be used it api response message.
    """
    number_of_requests, period = rate.split('/')
    number_of_requests = int(number_of_requests)
    period_count = period[:-1] or '1'
    period_unit = period[-1]
    return 'لطفا {count} {unit} صبر نمایید'.format(
        count=period_count,
        unit='ثانیه' if period_unit == 's' else 'دقیقه' if period_unit == 'm' else 'ساعت' if period_unit == 'h' else 'روز',
    )


def api(**method_rates):
    def decorator(view):
        @wraps(view)
        @api_view(list(method_rates.keys()))
        @authentication_classes([TokenAuthentication])
        @permission_classes([IsAuthenticated])
        def wrapped_view(request, *args, **kwargs):
            method = request.method
            if method not in method_rates:
                return HttpResponseNotAllowed(method_rates.keys())
            rate = method_rates[method]
            old_limited = getattr(request, 'limited', False)
            rate_limited = is_ratelimited(
                request=request,
                key='user_or_ip',
                fn=view,
                rate=rate,
                method=method,
                increment=True,
            )
            request.limited = rate_limited or old_limited
            if rate_limited:
                return JsonResponse({
                    'status': 'failed',
                    'message': f'تعداد درخواست شما بیش از حد معمول تشخیص داده شده.{translate_rate_limit_to_message(rate)}.',
                    'code': 'TooManyRequests'
                }, status=429)

            atomic_transaction = not method == 'GET'
            return run_api_view(view, request, atomic_transaction, *args, **kwargs,)

        wrapped_view.csrf_exempt = True
        return wrapped_view
    return decorator


def public_api(rate):
    def decorator(view):
        @wraps(view)
        @api_view(['GET'])
        @authentication_classes([TokenAuthentication])
        @permission_classes([])
        def wrapped_view(request, *args, **kwargs):
            old_limited = getattr(request, 'limited', False)
            rate_limited = is_ratelimited(
                request=request,
                key='user_or_ip',
                fn=view,
                rate=rate,
                method='GET',
                increment=True,
            )
            request.limited = rate_limited or old_limited
            if rate_limited:
                return JsonResponse({
                    'status': 'failed',
                    'message': f'تعداد درخواست شما بیش از حد معمول تشخیص داده شده.{translate_rate_limit_to_message(rate)}.',
                    'code': 'TooManyRequests'
                }, status=429)

            return run_api_view(view, request, False, *args, **kwargs,)

        wrapped_view.csrf_exempt = True
        return wrapped_view
    return decorator


def get_ratelimit_key_from_path(path_key: str):
    return lambda g, r: str(r.resolver_match.kwargs[path_key])


def internal_post_api(allowed_services: Iterable[Services], *, _idempotent=True):
    def outer_wrapper(view):
        @wraps(view)
        @log_api(is_internal=True)
        @api_view(['POST'])
        @authentication_classes([InternalAuthentication])
        @permission_classes([AllowedServices(allowed_services=allowed_services)])
        def wrapped_view(request, *args, **kwargs):
            _view = idempotent(view) if _idempotent else view
            try:
                return run_api_view_in_atomic_transaction(_view, request, *args, **kwargs)
            except Ratelimited:
                return handle_ratelimit()

        wrapped_view.csrf_exempt = True
        return wrapped_view

    return outer_wrapper


def internal_get_api(allowed_services: Iterable[Services]):
    def outer_wrapper(view):
        @wraps(view)
        @log_api(is_internal=True)
        @api_view(['GET'])
        @authentication_classes([InternalAuthentication])
        @permission_classes([AllowedServices(allowed_services=allowed_services)])
        def wrapped_view(request, *args, **kwargs):
            try:
                return run_raw_api_view(view, request, *args, **kwargs)
            except Ratelimited:
                return handle_ratelimit()

        wrapped_view.csrf_exempt = True
        return wrapped_view

    return outer_wrapper


class InternalAPIView(APIMixin, RestAPIView):
    authentication_classes = [InternalAuthentication]
    permission_classes = []
    renderer_classes = [JSONRenderer]

    @log_api(is_internal=True)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


def internal_access_api(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        ip = get_client_ip(request)
        if not is_nobitex_server_ip(ip or ''):
            raise Http404()
        return view(request, *args, **kwargs)

    return wrapper
