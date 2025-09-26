from hmac import compare_digest
from typing import Dict

from django.conf import settings
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions
from rest_framework.authentication import BasicAuthentication, TokenAuthentication

from exchange.asset_backed_credit.constant import USER_ID_HEADER
from exchange.asset_backed_credit.services.providers.provider import BasicAuthenticationSupportProvider
from exchange.asset_backed_credit.services.providers.provider_manager import provider_manager
from exchange.asset_backed_credit.services.user import get_or_create_internal_user


class DebitBasicAuthentication(BasicAuthentication):
    @staticmethod
    def _get_users() -> Dict[str, str]:
        return {
            p.api_username: p.api_password
            for p in provider_manager.providers
            if isinstance(p, BasicAuthenticationSupportProvider)
        }

    def _authenticate(self, request, username=None, password=None, **kwargs):
        users = self._get_users()
        if username not in users:
            return None

        user_password = users[username]
        if compare_digest(user_password, password):
            return User(is_active=True)

    def authenticate_credentials(self, userid, password, request=None):
        """
        Authenticate the userid and password against username and password
        with optional request for context.
        """
        credentials = {'username': userid, 'password': password}
        user = self._authenticate(request=request, **credentials)

        if user is None:
            raise exceptions.AuthenticationFailed(_('Invalid username/password.'))

        if not user.is_active:
            raise exceptions.AuthenticationFailed(_('User inactive or deleted.'))

        return user, None


class InternalTokenAuthentication(TokenAuthentication):
    def authenticate(self, request):
        if not settings.ABC_AUTHENTICATION_ENABLED:
            user_id = request.headers.get(USER_ID_HEADER)
            internal_user = get_or_create_internal_user(user_id)
            internal_user.is_authenticated = True
            return internal_user, None

        user_and_token = super().authenticate(request)
        if not user_and_token:
            return None
        user, token = user_and_token
        internal_user = get_or_create_internal_user(user.uid)
        request.internal_user = internal_user
        if not settings.ABC_AUTHENTICATION_INTERNAL_USER_ENABLED:
            return user, token

        internal_user.is_authenticated = True
        return internal_user, token
