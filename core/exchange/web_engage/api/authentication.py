from rest_framework import HTTP_HEADER_ENCODING
from rest_framework.authentication import BaseAuthentication

from exchange.base.models import Settings
from exchange.web_engage.api.exceptions import MalformedTokenHeader, WrongToken
from exchange.web_engage.types import ESPDeliveryStatusCode, SSPDeliveryStatusCode


class WebEngageAuthentication(BaseAuthentication):
    key_name = 'default'
    invalid_token_error_code = None

    @classmethod
    def get_authentication_token(cls, request) -> bytes:
        auth = request.headers.get('authorization', b'').strip()
        if isinstance(auth, str):
            # Work around django test client oddness
            auth = auth.encode(HTTP_HEADER_ENCODING)
        try:
            keyword, token = auth.split()
        except ValueError:
            raise MalformedTokenHeader(cls.invalid_token_error_code)
        if keyword.decode() != "Token":
            raise MalformedTokenHeader(cls.invalid_token_error_code)
        return token

    def authenticate(self, request):
        token = self.get_authentication_token(request)
        if Settings.get_value(self.key_name) != token.decode():
            raise WrongToken(self.invalid_token_error_code)
        return None, token


class DiscountAuthentication(WebEngageAuthentication):
    key_name = "webengage_journey_api_key"
    invalid_token_error_code = None


class SSPAuthentication(WebEngageAuthentication):
    key_name = "webengage_ssp_api_key"
    invalid_token_error_code = SSPDeliveryStatusCode.AUTHENTICATION_FAILURE.value


class ESPAuthentication(WebEngageAuthentication):
    key_name = "webengage_esp_api_key"
    invalid_token_error_code = ESPDeliveryStatusCode.AUTHENTICATION_FAILURE.value
