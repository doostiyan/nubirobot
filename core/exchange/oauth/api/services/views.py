from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from oauth2_provider.contrib.rest_framework.permissions import TokenHasScope
from rest_framework.permissions import IsAuthenticated

from exchange.base.api import APIView
from exchange.oauth.api.services.permissions import CheckIPAddress, UserIsActive
from exchange.oauth.api.services.serializers import (
    profile_info_serializer,
    user_identity_info_serializer,
    user_info_serializer,
)
from exchange.oauth.constants import Scopes


class BaseNobitexOauthView(APIView):
    permission_classes = [IsAuthenticated, TokenHasScope, CheckIPAddress, UserIsActive]
    authentication_classes = [OAuth2Authentication]
    required_scopes: list


class ProfileInfoView(BaseNobitexOauthView):
    """
    General profile information including user_id, email, and phone number
    """

    required_scopes = [Scopes.PROFILE_INFO.scope]

    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', method='GET', block=True))
    def get(self, request):
        data = profile_info_serializer(request.user, request.auth.application)
        return self.response({'status': 'ok', 'data': data})


class UserInfoView(BaseNobitexOauthView):
    """
    General user information including name, birthdate, and level
    """

    required_scopes = [Scopes.USER_INFO.scope]

    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', method='GET', block=True))
    def get(self, request):
        data = user_info_serializer(request.user)
        return self.response({'status': 'ok', 'data': data})


class IdentityInfoView(BaseNobitexOauthView):

    required_scopes = [Scopes.IDENTITY_INFO.scope]

    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', method='GET', block=True))
    def get(self, request):
        data = user_identity_info_serializer(request.user, request.auth.application)
        return self.response({'status': 'ok', 'data': data})
