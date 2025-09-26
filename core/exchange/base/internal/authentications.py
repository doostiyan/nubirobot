import jwt
from django.conf import settings
from django.http import Http404
from django.utils.translation import gettext_lazy as _
from ipware import get_client_ip
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, TokenAuthentication, get_authorization_header

from exchange.accounts.models import User
from exchange.base.api import is_nobitex_server_ip
from exchange.base.internal.errors import Errors
from exchange.base.internal.services import Services
from exchange.base.logging import report_event, report_exception
from exchange.base.models import Settings


class InternalAuthentication(BaseAuthentication):
    """
    Custom authentication class for internal service requests.

    This class performs authentication for requests by verifying that:
    - The request is coming from an internal instance as specified by `settings.IS_INTERNAL_INSTANCE`.
    - The request originates from a valid server IP address, as defined by `is_nobitex_server_ip`.
    - A valid JWT token is provided in the `Authorization` header of the request.

    The JWT token must be in the format "Bearer <token>". The token is then decoded using a list of public keys specified in `settings.INTERNAL_JWT_PUBLIC_KEYS`.

    If the token is valid and not blacklisted (according to `settings.BLACKLIST_JWTS`), the service identified by the token is extracted and assigned to `request.service`.
    """

    def authenticate(self, request):
        path = request.META['PATH_INFO']
        method = request.META['REQUEST_METHOD']
        ip = get_client_ip(request)[0]

        if not settings.IS_INTERNAL_INSTANCE:
            error = Errors.NOT_AN_INTERNAL_SERVER.value
            request.api_log['extras'].update({'error_code': error})
            report_event(error, attach_stacktrace=True)
            print(error, ip, method, path)
            raise Http404()

        # Skip the first args if it is self
        if (not ip or not is_nobitex_server_ip(ip)) and (
            not settings.IS_TESTNET or ip not in Settings.get_cached_json('internal_ip_whitelist', [])
        ):
            error = Errors.UNAUTHORIZED_IP.value
            request.api_log['extras'].update({'error_code': error})
            report_event(error, attach_stacktrace=True)
            print(error, ip, method, path)
            raise Http404()

        auth = get_authorization_header(request)
        if auth is None:
            error = Errors.MISSING_TOKEN.value
            request.api_log['extras'].update({'error_code': error})
            report_event(error, attach_stacktrace=True)
            print(error, ip, method, path)
            raise Http404()

        auth = auth.split()
        # Assuming the token is sent as "Bearer <token>"
        if len(auth) != 2 or auth[0] != b'Bearer':
            error = Errors.INVALID_TOKEN_FORMAT.value
            request.api_log['extras'].update({'error_code': error})
            report_event(error, attach_stacktrace=True)
            print(error, ip, method, path)
            raise Http404()

        token = auth[1].decode()

        for public_key in settings.INTERNAL_JWT_PUBLIC_KEYS:
            try:
                # Decode the token using the public keys
                payload = jwt.decode(token, public_key, algorithms=['RS256'], options=dict(verify_jti=False))
            except jwt.PyJWTError:
                # Just skip to try the next pubkey.
                report_exception()
                error = Errors.INVALID_TOKEN_SIGNATURE.value
                request.api_log['extras'].update({'error_code': error})
                print(error, ip, method, path)
                continue

            token_id = payload.get('jti')
            if token_id in settings.BLACKLIST_JWTS:
                error = Errors.BLACKLISTED_TOKEN.value
                request.api_log['extras'].update({'error_code': error})
                report_event(error, attach_stacktrace=True)
                print(error, ip, method, path)
                raise Http404()

            # Inject the service into the request
            service = payload.get('service')
            if service is None:
                error = Errors.TOKEN_WITHOUT_SERVICE.value
                request.api_log['extras'].update({'error_code': error})
                report_event(error, attach_stacktrace=True)
                print(error, ip, method, path)
                raise Http404()

            # Convert enum value to enum member
            try:
                request.service = Services(service).value
            except ValueError as ex:
                error = Errors.INVALID_SERVICE.value
                request.api_log['extras'].update({'error_code': error})
                report_event(error, attach_stacktrace=True)
                print(error, ip, method, path)
                raise Http404() from ex

            break
        else:
            # Token signature not matched with any pubkey
            error = Errors.UNKNOWN_TOKEN.value
            request.api_log['extras'].update({'error_code': error})
            report_event(error, attach_stacktrace=True)
            print(error, ip, method, path)
            raise Http404()


class InternalGatewayTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        model = self.get_model()
        try:
            user = User.objects.only('uid', 'user_type').get(auth_token__key=key, is_active=True)
        except (model.DoesNotExist, User.DoesNotExist) as ex:
            raise exceptions.AuthenticationFailed(_('Invalid token.')) from ex

        return (user, None)
