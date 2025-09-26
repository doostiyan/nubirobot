"""API Utilities"""
import base64
import json
import re
from functools import wraps
from ipaddress import AddressValueError, IPv4Address, IPv4Network

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.http.response import Http404, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.utils.datastructures import MultiValueDict
from django_ratelimit.exceptions import Ratelimited
from pydantic import BaseModel
from rest_framework import serializers
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView as RestAPIView
from rest_framework.views import exception_handler as drf_exception_handler

from exchange.base.logging import report_exception
from exchange.base.serializers import serialize


class APIException(Exception):
    pass


class ParseError(APIException):
    pass


class InternalAPIError(APIException):
    pass


class NobitexAPIError(APIException):
    def __init__(self, message, description=None, *, status_code=200):
        super().__init__(message)
        self.code = message
        self.description = description
        self.status_code = status_code


HTTP401 = NobitexAPIError(status_code=401, message='Unauthorized')


class SemanticAPIError(NobitexAPIError):
    pass


def is_internal_ip(ip: str) -> bool:
    """Check if the IP belongs to Nobitex or a trusted partner of it."""
    if not ip:
        return False
    if ip.startswith('94.182.183.'):
        return True
    return ip in [
        '37.27.13.213',
        '46.4.123.226',
        '65.109.111.169',
        '95.216.20.243',
        '95.216.77.44',
        '95.216.101.220',
        '95.217.35.23',
        '95.217.39.53',
        '95.217.41.198',
        '116.202.214.233',
    ]


def is_nobitex_server_ip(ip: str) -> bool:
    """Check if IP Belongs to Nobitex Servers"""
    if not ip:
        return False
    try:
        _ip = IPv4Address(ip)
    except AddressValueError:
        return False
    return any(_ip in IPv4Network(network) for network in settings.NOBITEX_SERVER_IPS if network)


def get_data(request):
    """ This function get data and files from request

        :param request: Django Request
        :return: List of Posted Data and List of Posted Files
    """
    posted_data = {}
    posted_files = {}
    body = request.body

    if request.method == "DELETE":
        posted_data = request.GET
        return posted_data, posted_files

    if request.method == 'GET':
        return request.GET, posted_files

    if not posted_data and body:
        if not posted_data:
            try:
                posted_data = json.loads(body.decode("utf-8").replace("'", "\""))
            except ValueError:
                posted_data = {}
                try:
                    temp_file = TemporaryUploadedFile("temp.apk", "application/octet-stream", len(body), "utf-8")
                    temp_file.file.write(body)
                    posted_files = MultiValueDict({"apk_file": [temp_file]})
                except ValueError:
                    posted_files = {}

    if request.content_type.startswith("application/x-www-form-urlencoded") \
            or request.content_type.startswith("multipart/form-data"):
        posted_data = request.POST
        if not posted_files:
            posted_files = request.FILES

    return posted_data, posted_files


def get_user_by_token(request):
    """ Get the user from request authorization token """
    if request.user.is_authenticated:
        return request.user
    try:
        auth = TokenAuthentication().authenticate(request)
    except AuthenticationFailed:
        return AnonymousUser()
    if not auth:
        return AnonymousUser()
    return auth[0]


def is_request_from_unsupported_app(request):
    """Check if this request is from an Android app with old version."""
    ua = (request.headers.get('user-agent') or 'unknown')[:255]
    return ua.startswith('Android/') and ua < f'Android/{settings.LAST_SUPPORTED_ANDROID_VERSION}'


def compare_versions(version1, version2):
    version1_components = version1.split('.')
    version2_components = version2.split('.')

    # Check if patch version is missing and set it to 0
    if len(version1_components) < 3:
        version1_components.append('0')
    if len(version2_components) < 3:
        version2_components.append('0')

    # Compare major version
    if int(version1_components[0]) > int(version2_components[0]):
        return 1
    elif int(version1_components[0]) < int(version2_components[0]):
        return -1

    # Compare minor version
    if int(version1_components[1]) > int(version2_components[1]):
        return 1
    elif int(version1_components[1]) < int(version2_components[1]):
        return -1

    # Compare patch version
    if int(version1_components[2]) > int(version2_components[2]):
        return 1
    elif int(version1_components[2]) < int(version2_components[2]):
        return -1

    # Versions are equal
    return 0


def handle_exception(e):
    if isinstance(e, ParseError) or isinstance(e, serializers.ValidationError):
        return JsonResponse(status=400, data={'status': 'failed', 'code': 'ParseError', 'message': str(e)})
    if isinstance(e, SemanticAPIError):
        return JsonResponse(status=422, data={'status': 'failed', 'code': e.code, 'message': e.description or e.code})
    if isinstance(e, NobitexAPIError):
        return JsonResponse(
            status=e.status_code, data={'status': 'failed', 'code': e.code, 'message': e.description or e.code}
        )
    if isinstance(e, (Http404, InternalAPIError)):
        return JsonResponse(status=404, data={'message': getattr(e, 'message', str(e)), 'error': 'NotFound'})
    if isinstance(e, Ratelimited):
        return handle_ratelimit()
    event_id = report_exception()
    if settings.DEBUG:
        raise e
    return JsonResponse(
        status=400,
        data={
            'status': 'failed',
            'code': 'UnexpectedError',
            'message': 'We cannot proceed with your request.',
            'eventId': event_id,
        }
    )


def handle_ratelimit():
    return JsonResponse(
        {
            'status': 'failed',
            'message': 'تعداد درخواست شما بیش از حد معمول تشخیص داده شده. لطفا کمی صبر نمایید.',
            'code': 'TooManyRequests',
        },
        status=429,
    )


def run_api_view(view, request, *args, **kwargs):
    # Parse request data
    data, request.uploaded_files = get_data(request)
    if isinstance(data, str) and data == '':
        data = {}
    if data is None:
        data = {}
    if data == []:
        data = {}

    def g(k, default=None):
        return data.get(k, default)

    request.g = g

    # Run and track exceptions
    try:
        r = view(request, *args, **kwargs)
    except Exception as e:
        return handle_exception(e)

    if not isinstance(r, HttpResponse):
        if isinstance(r, BaseModel):
            r = HttpResponse(r.model_dump_json(by_alias=True), content_type='application/json')
        else:
            r = JsonResponse(serialize(r), safe=False)
    return r


def api(view, *args, **kwargs):
    @wraps(view)
    @api_view(['GET', 'POST'])
    @authentication_classes([TokenAuthentication])
    @permission_classes([IsAuthenticated])
    def wrapped_view(request, *args, **kwargs):
        if getattr(request, 'limited', False):
            return handle_ratelimit()
        return run_api_view(view, request, *args, **kwargs)
    wrapped_view.csrf_exempt = True
    return wrapped_view


def get_api(view, *args, **kwargs):
    @wraps(view)
    @api_view(['GET'])
    @authentication_classes([TokenAuthentication])
    @permission_classes([IsAuthenticated])
    def wrapped_view(request, *args, **kwargs):
        if getattr(request, 'limited', False):
            return handle_ratelimit()
        return run_api_view(view, request, *args, **kwargs)
    wrapped_view.csrf_exempt = True
    return wrapped_view


def post_api(view, *args, **kwargs):
    @wraps(view)
    @api_view(['POST'])
    @authentication_classes([TokenAuthentication])
    @permission_classes([IsAuthenticated])
    def wrapped_view(request, *args, **kwargs):
        if getattr(request, 'limited', False):
            return handle_ratelimit()
        return run_api_view(view, request, *args, **kwargs)
    wrapped_view.csrf_exempt = True
    return wrapped_view


def api_with_perms(permissions):
    def _method_wrapper(view):
        @wraps(view)
        @api_view(['GET', 'POST'])
        @authentication_classes([TokenAuthentication])
        @permission_classes(permissions)
        def wrapped_view(request, *args, **kwargs):
            if getattr(request, 'limited', False):
                return handle_ratelimit()
            return run_api_view(view, request, *args, **kwargs)

        wrapped_view.csrf_exempt = True
        return wrapped_view
    return _method_wrapper


def public_api(view):
    @wraps(view)
    def wrapped_view(request, *args, **kwargs):
        if request.method != 'GET':
            return HttpResponseNotAllowed(['GET'])
        return run_api_view(view, request, *args, **kwargs)
    wrapped_view.csrf_exempt = True
    return wrapped_view


# Temporary public post method
def public_post_v2_api(view):
    @wraps(view)
    def wrapped_view(request, *args, **kwargs):
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        return run_api_view(view, request, *args, **kwargs)
    wrapped_view.csrf_exempt = True
    return wrapped_view


def public_post_api(view):
    @wraps(view)
    @api_view(['POST'])
    @authentication_classes([])
    @permission_classes([])
    def wrapped_view(request):
        return run_api_view(view, request)
    wrapped_view.csrf_exempt = True
    return wrapped_view


def public_get_and_post_api(view):
    @wraps(view)
    @api_view(['POST', 'GET'])
    @authentication_classes([])
    @permission_classes([])
    def wrapped_view(request):
        return run_api_view(view, request)
    wrapped_view.csrf_exempt = True
    return wrapped_view


def basic_auth_api(view):
    @wraps(view)
    @api_view(['POST'])
    def wrapped_view(request):
        # Check for valid basic auth header
        auth = request.headers.get('HTTP_AUTHORIZATION') or request.headers.get('authorization')
        if auth:
            auth = auth.split()
            if len(auth) == 2:
                if auth[0].lower() == "basic":
                    username, password = base64.b64decode(auth[1]).decode('utf-8').split(':')
                    return view(request, username, password)

        # Either they did not provide an authorization header or
        # something in the authorization attempt failed. Send a 401
        # back to them to ask them to authenticate.
        response = HttpResponse()
        response.status_code = 401
        basic_realm = ""
        response['WWW-Authenticate'] = 'Basic realm="%s"' % basic_realm
        return response

    wrapped_view.csrf_exempt = True
    return wrapped_view


# Utilities for class-based views
class APIMixin:
    def g(self, k, default=None):
        try:
            data = self._request_data
        except AttributeError:
            data = self._request_data = get_data(self.request)[0]
        return data.get(k, default)

    @staticmethod
    def response(obj, opts=None):
        if not isinstance(obj, HttpResponse):
            obj = JsonResponse(serialize(obj, opts=opts), safe=False)
        return obj

    def handle_exception(self, exc):
        if isinstance(exc, Ratelimited):
            raise exc
        try:
            return super(APIMixin, self).handle_exception(exc)
        except Exception as e:
            return handle_exception(e)

    def is_from_unsupported_app(self, feature: str) -> bool:
        from exchange.base.helpers import is_from_unsupported_app

        return is_from_unsupported_app(request=self.request, feature=feature)


class APIView(APIMixin, RestAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]


class PublicAPIView(APIMixin, RestAPIView):
    authentication_classes = []
    permission_classes = []
    renderer_classes = [JSONRenderer]


class NobitexAPIMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if not isinstance(exception, Ratelimited):
            return None
        return handle_ratelimit()


def raise_on_email_not_verified(user):
    from exchange.accounts.userlevels import UserLevelManager
    if not UserLevelManager.is_eligible_for_email_required_services(user):
        raise NobitexAPIError('UnverifiedEmail', 'User does not have a verified email.', status_code=400)


def email_required_api(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        raise_on_email_not_verified(request.user)
        return view(request, *args, **kwargs)
    return wrapped


re_404_detail_pattern = re.compile(r'No \w+ matches the given query.')


def exception_handler(exc, context):
    # To keep the detail of 404 raised by get_object_or_404 be the same as drf v13, یافت نشد.
    if isinstance(exc, Http404) and len(exc.args) == 1 and re_404_detail_pattern.match(exc.args[0]):
        exc.args = ()

    # Call REST framework's default exception handler to get the standard error response.
    return drf_exception_handler(exc, context)
