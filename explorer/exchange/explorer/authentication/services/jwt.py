import sha3

from rest_framework_simplejwt.authentication import JWTStatelessUserAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework.exceptions import NotAuthenticated

from ...authentication.dtos import JWTAuthDTO, JWTAuthDTOCreator
from ..models import User


def get_auth_token_dto_for_user(user) -> JWTAuthDTO:
    refresh = TokenObtainPairSerializer.get_token(user)
    jwt_auth_dto = JWTAuthDTOCreator.get_dto({'access': str(refresh.access_token), 'refresh': str(refresh)})
    return jwt_auth_dto


def decode_token(token_str, token_type):
    if token_type == 'access':
        token_class = AccessToken
    else:
        token_class = RefreshToken
    return token_class(token_str)


def has_expired(token):
    try:
        token.check_exp()
        return False
    except TokenError:
        return True


def get_hash_token(token: str):
    return sha3.sha3_256(token.encode()).hexdigest()


class APIAuthentication(JWTStatelessUserAuthentication):
    def authenticate(self, request):
        format = request.accepted_renderer.format
        if format == 'html':
            raw_token_str = request.COOKIES.get('access_token')
            if raw_token_str:
                raw_token = str.encode(raw_token_str)
            else:
                return None
        else:
            header = self.get_header(request)
            if header is None:
                return None
            raw_token = self.get_raw_token(header)
            if raw_token is None:
                return None

        validated_token = self.get_validated_token(raw_token)

        return self.get_user(validated_token), validated_token


class StatefulAPIAuthentication(APIAuthentication):
    def authenticate(self, request):
        auth_result = super().authenticate(request)
        if auth_result:
            token_user, access_token = auth_result
            return User.objects.get(id=token_user.id), access_token
