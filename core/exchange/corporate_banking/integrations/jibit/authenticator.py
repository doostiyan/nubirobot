from requests import HTTPError

from exchange.base.logging import report_event
from exchange.base.models import Settings
from exchange.corporate_banking.config import COBANK_JIBIT_API_KEY, COBANK_JIBIT_SECRET_KEY
from exchange.corporate_banking.exceptions import ThirdPartyAuthenticationException
from exchange.corporate_banking.integrations.jibit.base import BaseJibitAPIClient
from exchange.corporate_banking.integrations.jibit.config import (
    JIBIT_ACCESS_TOKEN_SETTINGS_KEY,
    JIBIT_REFRESH_TOKEN_SETTINGS_KEY,
    get_base_url,
)
from exchange.corporate_banking.integrations.jibit.dto import AuthenticationTokenData


class CobankJibitAuthenticator(BaseJibitAPIClient):
    """
    A class to get access token and refresh token for Jibit's cobanking services based on OAuth 2.0
    documentation: https://napi.jibit.ir/cobank/swagger-ui/index.html#/token-controller/generateToken

    - get_auth_token() will be called the first time we need to call Jibit's APIs,
      after that in a happy scenario it should never be called because tokens should be refreshed.
      If refreshing tokens doesn't work correctly, get_auth_token() should be called again (e.g. in case of 401 error)
    """

    provider = 'jibit'
    api_url = 'v1/tokens/generate'
    refresh_api_url = 'v1/tokens/refresh'
    request_method = 'POST'
    metric_name = 'cobanking_thirdparty_services__Jibit_auth_'
    scopes = [
        'ACCOUNTS',
        'AUG_STATEMENT',
        'AUG_STATEMENT_VARIZ',
        'VARIZ_PID',
        'SETTLEMENT',
        'BALANCE',
    ]
    access_token_settings_key = JIBIT_ACCESS_TOKEN_SETTINGS_KEY
    refresh_token_settings_key = JIBIT_REFRESH_TOKEN_SETTINGS_KEY

    def __init__(self):
        super().__init__()
        self.base_url = get_base_url()

    def get_auth_token(self) -> str:
        response = self._send_request(self.headers, self._get_auth_data(), retry=2)
        return self.process_token_response(response)

    def refresh_token(self):
        refresh_token = Settings.get_value(self.refresh_token_settings_key)
        if not refresh_token:
            return self.get_auth_token()
        access_token = Settings.get_value(self.access_token_settings_key)
        try:
            response = self._send_request(
                self.headers,
                {'accessToken': access_token, 'refreshToken': refresh_token},
                api_url=self.refresh_api_url,
                retry=2,
            )
        except HTTPError as ex:
            if ex.response is not None and ex.response.status_code == 401:
                return self.get_auth_token()

            raise

        self.process_token_response(response)

    def process_token_response(self, token_response: dict) -> str:
        try:
            auth_data = AuthenticationTokenData(**token_response)
            Settings.set(self.access_token_settings_key, auth_data.accessToken)
            Settings.set(self.refresh_token_settings_key, auth_data.refreshToken)
            return auth_data.accessToken
        except TypeError as e:
            if 'errors' in token_response:
                self.handle_error(token_response)
            report_event(
                'CobankJibitClient_failed_to_get_auth_token',
                attach_stacktrace=True,
                extras={'error': f'error {e}', 'data': token_response},
            )

    def handle_error(self, token_response: dict):
        errors = token_response.get('errors', [])
        error_details = errors[0] if isinstance(errors, list) else errors
        error_code = error_details.get('code', '')
        error_message = error_details.get('message', '')
        report_event(
            'CobankJibitClient_failed_to_get_auth_token',
            extras={'error_code': error_code, 'error_message': error_message, 'errors': errors},
        )
        raise ThirdPartyAuthenticationException(error_code, error_message)

    def _get_auth_data(self):
        return {'apiKey': COBANK_JIBIT_API_KEY, 'secretKey': COBANK_JIBIT_SECRET_KEY, 'scopes': self.scopes}

