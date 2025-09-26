from functools import wraps

from django.conf import settings
from django.http.response import Http404
from rest_framework.decorators import api_view, permission_classes

from exchange.base.api import run_api_view
from exchange.base.http import get_basic_auth_credentials


def monitoring_api(view):
    @wraps(view)
    @api_view(['POST', 'GET'])
    @permission_classes([])
    def wrapped_view(request):
        has_access = settings.DEBUG
        if not has_access:
            username, password = get_basic_auth_credentials(request)
            has_access = username == settings.MONITORING_USERNAME and password == settings.MONITORING_PASSWORD
        if not has_access:
            raise Http404
        return run_api_view(view, request)

    wrapped_view.csrf_exempt = True
    return wrapped_view
