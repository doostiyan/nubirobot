import requests
from django.conf import settings
from rest_framework import status

from exchange.base.logging import report_event
from exchange.base.models import Settings
from exchange.corporate_banking.config import (
    COBANK_TOMAN_CLIENT_ID,
    COBANK_TOMAN_CLIENT_SECRET,
    COBANK_TOMAN_PASSWORD,
    COBANK_TOMAN_USERNAME,
)
from exchange.corporate_banking.exceptions import ThirdPartyAuthenticationException
from exchange.corporate_banking.integrations.base import BaseThirdPartyAPIClient
from exchange.corporate_banking.integrations.toman.dto import AuthenticationTokenData


class CobankTomanAuthenticator(BaseThirdPartyAPIClient):
    """
    A class to get access token and refresh token for Toman's cobanking services based on OAuth 2.0
    documentation: https://docs.tomanpay.net/corporate_banking/?python#get-access-token

    - get_auth_token() will be called the first time we need to call Toman's APIs,
      after that in a happy scenario it should never be called because tokens should be refreshed.
      If refreshing tokens doesn't work correcrly, get_auth_token() should be called again (e.g. in case of 401 error)
    - refresh_token() will be called through scheduled celery tasks to refresh the tokens
    - process_token_response() will set tokens in Settings and schedule a refresh_token() for near future
    """

    provider = 'toman'
    base_url = 'https://accounts.qbitpay.org/{}' if settings.IS_PROD else 'https://auth.qbitpay.org/{}'
    api_url = 'oauth2/token/'
    request_method = 'POST'
    metric_name = 'cobanking_thirdparty_services__Toman_auth_'
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    scopes = (
        'digital_banking.account.read '
        'digital_banking.statement.read '
        'digital_banking.transfer.read '
        'digital_banking.transfer.create '
        'digital_banking.transfer.execute '
        'digital_banking.transfer.cancel '
        'digital_banking.transfer.generate_receipt '
        'digital_banking.revert.read '
        'digital_banking.revert.create'
    )
    access_token_settings_key = 'cobank_toman_access_token'
    refresh_token_settings_key = 'cobank_toman_refresh_token'

    def __init__(self):
        if settings.IS_TESTNET and Settings.get_value('cobank_qa_test_server', 'yes'):
            self.base_url = 'https://wiremock-core-testnet.c62.darkube.app/toman-cobank/{}'

    def get_auth_token(self) -> str:
        data = {
            'client_id': COBANK_TOMAN_CLIENT_ID,
            'client_secret': COBANK_TOMAN_CLIENT_SECRET,
            'username': COBANK_TOMAN_USERNAME,
            'password': COBANK_TOMAN_PASSWORD,
            'grant_type': 'password',
            'scope': self.scopes,
        }

        response = self._send_request(self.headers, data, retry=2)
        return self.process_token_response(response)

    def refresh_token(self):
        refresh_token = Settings.get(self.refresh_token_settings_key, None)
        if not refresh_token:
            self.get_auth_token()
            return

        data = {
            'client_id': COBANK_TOMAN_CLIENT_ID,
            'client_secret': COBANK_TOMAN_CLIENT_SECRET,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
        }

        try:
            response = self._send_request(self.headers, data, retry=2)
        except requests.HTTPError as ex:
            if ex.response is not None and ex.response.status_code in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_400_BAD_REQUEST,
            ):
                self.get_auth_token()
                return

            raise

        self.process_token_response(response)

    def process_token_response(self, token_response: dict) -> str:
        try:
            auth_data = AuthenticationTokenData(**token_response)
            Settings.set(self.access_token_settings_key, auth_data.access_token)
            Settings.set(self.refresh_token_settings_key, auth_data.refresh_token)
            return auth_data.access_token
        except TypeError as e:
            if 'error' in token_response:
                self.handle_error(token_response)
            report_event(
                'CobankTomanClient_failed_to_get_auth_token',
                attach_stacktrace=True,
                extras={'error': f'error {e}', 'data': token_response},
            )

    def handle_error(self, token_response: dict):
        # In this case there is no point in retrying because there is a problem with our scopes, grants, client, etc
        error = token_response.get('error')
        description = token_response.get('error_description', '')
        report_event('CobankTomanClient_failed_to_get_auth_token', extras={'error': error, 'description': description})
        raise ThirdPartyAuthenticationException(error, description)
