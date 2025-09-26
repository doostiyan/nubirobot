from typing import ClassVar, Dict, Optional

from exchange.base.models import Settings
from exchange.corporate_banking.exceptions import ThirdPartyClientUnavailable
from exchange.corporate_banking.integrations.base import BaseThirdPartyAPIClient
from exchange.corporate_banking.integrations.jibit.config import JIBIT_ACCESS_TOKEN_SETTINGS_KEY, get_base_url


class BaseJibitAPIClient(BaseThirdPartyAPIClient):
    provider = 'jibit'

    access_token_settings_key = JIBIT_ACCESS_TOKEN_SETTINGS_KEY
    headers: ClassVar = {'content-type': 'application/json'}

    def __init__(self):
        super().__init__()
        self.base_url = get_base_url()

    def _send_request(
        self,
        headers: dict,
        payload: dict,
        *,
        retry: int = 0,
        api_url=None,
        is_json: bool = True,
        **kwargs,
    ) -> Optional[Dict]:
        return super()._send_request(headers, payload, retry=retry, api_url=api_url, is_json=is_json, **kwargs)

    def _prepare_headers(self):
        auth_token = Settings.get_value(self.access_token_settings_key)
        if not auth_token:
            from exchange.corporate_banking.integrations.jibit.authenticator import CobankJibitAuthenticator

            auth_token = CobankJibitAuthenticator().get_auth_token()

        return {
            'Authorization': f'Bearer {auth_token}',
            'content-type': 'application/json',
        }

    def _extract_exception(self, e: Exception, response: Optional[dict]) -> ThirdPartyClientUnavailable:
        errors = response.get('errors') if response else None
        error_code = errors[0].get('code', '') if isinstance(errors, list) else ''
        error_message = errors[0].get('message', '') if isinstance(errors, list) else 'Unknown error'

        raise ThirdPartyClientUnavailable(
            code=e.__class__.__name__,
            message=(
                f'Jibit Client Currently Unavailable: {e}, '
                f'error code: {error_code}, error message: {error_message}, errors: {errors}'
            ),
            status_code=e.response.status_code if getattr(e, 'response', None) and e.response.status_code else -1,
        )
