from django.conf import settings

from exchange.base.models import Settings
from exchange.corporate_banking.integrations.base import BaseThirdPartyAPIClient
from exchange.corporate_banking.integrations.toman.authenticator import CobankTomanAuthenticator


class BaseTomanAPIClient(BaseThirdPartyAPIClient):
    provider = 'toman'

    access_token_settings_key = 'cobank_toman_access_token'

    def __init__(self):
        self.base_url = (
            'https://dbank.toman.ir/api/v1{}' if settings.IS_PROD else 'https://dbank-staging.qcluster.org/api/v1{}'
        )
        if settings.IS_TESTNET and Settings.get_value('cobank_qa_test_server', 'yes'):
            self.base_url = 'https://wiremock-core-testnet.c62.darkube.app/toman-cobank{}'


    def _prepare_headers(self):
        auth_token = Settings.get_value(self.access_token_settings_key)
        if not auth_token:
            auth_token = CobankTomanAuthenticator().get_auth_token()
        return {
            'Authorization': f'Bearer {auth_token}',
            'content-type': 'application/json',
        }
