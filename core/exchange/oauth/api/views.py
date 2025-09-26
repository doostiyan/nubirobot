import base64
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from oauth2_provider.exceptions import FatalClientError, OAuthToolkitError
from oauth2_provider.views.base import TokenView as BaseTokenView
from oauth2_provider.views.mixins import OAuthLibMixin
from oauthlib.oauth2 import InvalidClientIdError, InvalidRedirectURIError, MismatchingRedirectURIError
from rest_framework import status

from exchange.base.api import APIView, NobitexAPIError
from exchange.base.http import get_client_ip
from exchange.base.parsers import parse_str
from exchange.oauth.api.decorators import standardise_oauth2_provider_api
from exchange.oauth.constants import AVAILABLE_RESPONSE_TYPE, DEFAULT_RESPONSE_TYPE
from exchange.oauth.exceptions import AuthorizationException, InactiveUser
from exchange.oauth.helpers import get_latest_tokens, get_unauthorized_scopes_of_app, raise_error_from_uri
from exchange.oauth.models import Application, Grant, RefreshToken


class ApplicationView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='12/m', method='GET', block=True))
    def get(self, request, client_id):
        """
        A GET API to get the information of a client using its client id and explanations of the scopes
        at url 'base_url/oauth/client/<str:client_id>'
        This API can be used when we want to inform the user that a client wants to access what scopes of their data.
        The data passed to the API can include 'scopes':
            - if it doesn't, we only return the explanations of all the client's scopes
            - if it does, we return the explanations of any unauthorized scope which exists within client's scopes
        e.g. if the client's scopes are 'profile-info wallet':
            - if data doesn't include scopes, we return the explanations of 'profile-info' and 'wallet' scopes
            - if data includes {'scopes': 'profile-info other'}, we only return the explanation of 'profile-info' scope
                if it isn't previously authorized by the user. If user has authorized 'profile-info', we return an
                empty list of scopes.
        Args:
            client_id: the client's client_id

        Returns:
            The client's name and the explanation of scopes
        """
        user = request.user
        scopes = parse_str(self.g('scopes', None), required=False)

        try:
            application = Application.objects.get_by_natural_key(client_id=client_id)
        except ObjectDoesNotExist as e:
            raise NobitexAPIError(
                message='NotFound', description='Client not found', status_code=status.HTTP_404_NOT_FOUND
            )

        common_scopes = application.get_common_scopes(scopes)
        unauthorized_scopes = get_unauthorized_scopes_of_app(user=user, app=application, scopes=common_scopes)

        return self.response(
            {'status': 'ok', 'data': application},
            opts={'scopes': unauthorized_scopes},
        )


class AuthorizationAPIView(APIView, OAuthLibMixin):
    """
    Implements an endpoint to handle *Authorization Requests* as in
    https://www.rfc-editor.org/rfc/rfc6749.html#section-4.1
    """

    @method_decorator(ratelimit(key='user_or_ip', rate='30/h', method='post', block=True))
    def post(self, request):
        client_id = parse_str(self.g('clientId'), required=True)
        redirect_uri = parse_str(self.g('redirectUri'), required=True)
        scope = parse_str(self.g('scope'), required=True)
        state = parse_str(self.g('state'), required=True)
        code_challenge = parse_str(self.g('codeChallenge'), required=True)
        code_challenge_method = parse_str(self.g('codeChallengeMethod'), required=True)
        response_type = parse_str(self.g('responseType'), required=False) or DEFAULT_RESPONSE_TYPE

        credentials = {
            'state': state,
            'response_type': response_type,
            'redirect_uri': redirect_uri,
            'client_id': client_id,
            'code_challenge': code_challenge,
            'code_challenge_method': code_challenge_method,
        }
        try:
            if response_type not in AVAILABLE_RESPONSE_TYPE:
                raise AuthorizationException(code='UnsupportedResponseType', message='Unsupported response_type.')

            application = Application.objects.get_by_natural_key(client_id=client_id)
            if not application.allow_scopes(scope):
                raise AuthorizationException(code='InvalidScope', message='Scope is invalid.')
            uri, headers, body, response_status = self.create_authorization_response(
                request=self.request, scopes=scope, credentials=credentials, allow=True
            )
            raise_error_from_uri(uri)
        except FatalClientError as e:
            if isinstance(e.oauthlib_error, InvalidRedirectURIError):
                return JsonResponse(
                    {
                        'status': 'failed',
                        'code': 'InvalidRedirectURI',
                        'message': 'Redirect_uri is invalid.',
                        'state': state,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            elif isinstance(e.oauthlib_error, InvalidClientIdError):
                return JsonResponse(
                    {'status': 'failed', 'code': 'InvalidClientID', 'message': 'Client_id is Invalid.', 'state': state},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            elif isinstance(e.oauthlib_error, MismatchingRedirectURIError):
                return JsonResponse(
                    {'status': 'failed', 'code': 'MismatchingRedirectURIError', 'message': 'Mismatching redirect URI.', 'state': state},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                return JsonResponse(
                    {'status': 'failed', 'code': 'InvalidRequest', 'message': 'Request is invalid.', 'state': state},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except OAuthToolkitError as e:
            return JsonResponse(
                {'status': 'failed', 'code': 'UnexpectedError', 'message': 'Unexpected error', 'state': state},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except AuthorizationException as e:
            return JsonResponse(
                {'status': 'failed', 'code': e.code, 'message': e.message, 'state': state},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ObjectDoesNotExist as e:
            return JsonResponse(
                {'status': 'failed', 'code': 'NotFound', 'message': 'Client not found', 'state': state},
                status=status.HTTP_404_NOT_FOUND,
            )
        data = {'redirectUri': uri, 'state': state}
        return self.response({'status': 'ok', 'data': data})


def oauth_token_ratelimit(group, request):
    """
    :return: increased ratelimit for Nova game in campaign
    """
    ip = request.META['REMOTE_ADDR']
    return '100/1m' if ip == '185.73.202.3' else '20/10m'


@method_decorator(ratelimit(key='ip', rate=oauth_token_ratelimit), name='dispatch')
@method_decorator(standardise_oauth2_provider_api, name='post')
class TokenView(BaseTokenView):
    """Generate access token from authorization code

    This endpoint shall be called from client's server, therefore is protected by IP check.

        URL:
            POST /oauth/token

        Request Headers:
            Authorization: Basic authorization of client's client_id and client_secret (before encryption on save)

        Request Body Params:
            grantType: `authorization_code` or `refresh_token`

            1. `authorization_code` mode:
            - code: the user's grant authorization_code - required in `authorization_code` grant type
            - codeVerifier: the client's code_verifier of PKCE protocol - required in `authorization_code` grant type
            - redirectUri: the URI which user is about to be redirected to after authorization

            2. `refresh_token` mode:
            - refreshToken: the user's refresh token - required in `refresh_token` grant type

        Response Params:
            accessToken: the token to use for getting authorized access to user's data
            refreshToken: tho token to use for refreshing access token after expiry
            tokenType: type of the generated token, defaults to `Bearer`
            expiresIn: access token expiry in seconds, defaults to settings.ACCESS_TOKEN_EXPIRE_SECONDS
            scope: the space-separated scopes to which the access token can reach
    """

    def post(self, request, *args, **kwargs):
        try:
            self.check_permissions()
        except ObjectDoesNotExist as e:
            return JsonResponse({'status': 'failed', 'error': 'invalid_grant'}, status=status.HTTP_400_BAD_REQUEST)
        except (InactiveUser, AuthorizationException) as e:
            return JsonResponse({'error': e.code, 'error_description': e.message}, status=status.HTTP_403_FORBIDDEN)
        return super().post(request, *args, **kwargs)

    def check_permissions(self) -> None:
        client_id = self.get_client_id()
        if not client_id:
            raise ObjectDoesNotExist
        application = Application.objects.get_by_natural_key(client_id=client_id)
        auth_code = self.request.POST.get('code')
        refresh_code = self.request.POST.get('refresh_token')
        if auth_code:
            grant = Grant.objects.filter(application=application, code=auth_code).select_related('user').first()
            if not grant:
                raise ObjectDoesNotExist
            if not grant.user.is_active:
                raise InactiveUser(code='unavailable_user', message='Cannot be authorized for this user.')
        elif refresh_code:
            refresh_token = (
                RefreshToken.objects.filter(application=application, token=refresh_code).select_related('user').first()
            )
            if not refresh_token:
                raise ObjectDoesNotExist
            if not refresh_token.user.is_active:
                raise InactiveUser(code='unavailable_user', message='Cannot be authorized for this user.')

        ip = get_client_ip(self.request)
        if not application.accepts_ip(ip):
            raise AuthorizationException(code='invalid_ip', message='Invalid ip')

    def get_client_id(self) -> Optional['str']:
        if 'authorization' in self.request.headers:
            auth_string = self.request.headers['authorization']
            try:
                assert auth_string.startswith('Basic ')
                return base64.b64decode(auth_string[6:]).decode('utf8').split(':')[0]
            except (AssertionError, UnicodeDecodeError, KeyError):
                return None
        return self.request.POST.get('client_id')


class GrantedAccessesView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='5/m', method='GET', block=True))
    def get(self, request):
        user = request.user
        granted_accesses = get_latest_tokens(user=user).prefetch_related('application')

        return self.response(
            {
                'status': 'ok',
                'grantedAccesses': granted_accesses,
            }
        )
