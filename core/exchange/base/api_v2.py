"""API Utilities v2

The goal of this module is providing
a decorator that run `POST` (and only `POST`)
apis in one DB transactions.
"""

__all__ = [
    'NobitexAPIError',
    'public_api',
    'post_api',
    'get_api',
    'api'
]

from functools import wraps

from django.db import transaction
from django.http.response import HttpResponse, JsonResponse
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from exchange.base.api import NobitexAPIError, get_api, get_data, handle_exception, public_api
from exchange.base.serializers import serialize


def run_api_view_in_atomic_transaction(view, request, *args, **kwargs):
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
        with transaction.atomic():
            # view should return `{'status': 'ok', ...}` or raise an `Exception`
            r = view(request, *args, **kwargs)
    except Exception as e:
        return handle_exception(e)
    if not isinstance(r, HttpResponse):
        r = JsonResponse(serialize(r), safe=False)
    return r


def api(view, *args, **kwargs):
    @wraps(view)
    @api_view(['GET', 'POST'])
    @authentication_classes([TokenAuthentication])
    @permission_classes([IsAuthenticated])
    def wrapped_view(request, *args, **kwargs):
        if getattr(request, 'limited', False):
            return JsonResponse({'status': 'failed', 'message': 'تعداد درخواست شما بیش از حد معمول تشخیص داده شده. لطفا یک ساعت صبر نمایید.', 'code': 'TooManyRequests'}, status=429)
        return run_api_view_in_atomic_transaction(view, request, *args, **kwargs)
    wrapped_view.csrf_exempt = True
    return wrapped_view


def post_api(view, *args, **kwargs):
    @wraps(view)
    @api_view(['POST'])
    @authentication_classes([TokenAuthentication])
    @permission_classes([IsAuthenticated])
    def wrapped_view(request, *args, **kwargs):
        if getattr(request, 'limited', False):
            return JsonResponse({'status': 'failed', 'message': 'تعداد درخواست شما بیش از حد معمول تشخیص داده شده. لطفا یک ساعت صبر نمایید.', 'code': 'TooManyRequests'}, status=429)
        return run_api_view_in_atomic_transaction(view, request, *args, **kwargs)
    wrapped_view.csrf_exempt = True
    return wrapped_view
