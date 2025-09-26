from typing import Dict, Optional

import requests
from django.core.cache import cache

from exchange.base.models import Settings
from exchange.corporate_banking.utils import ObjectBasedMetricMeasurement


def remove_tokens(access_token_settings_key: str, refresh_token_settings_key: str):
    Settings.objects.filter(key__in=[access_token_settings_key, refresh_token_settings_key]).delete()

    cache.delete(Settings.RELATED_CACHE_KEYS.get(access_token_settings_key)[0])
    cache.delete(Settings.RELATED_CACHE_KEYS.get(refresh_token_settings_key)[0])


class BaseThirdPartyAPIClient:
    provider: str
    base_url: str
    api_url: str
    request_method: str
    metric_name: str
    timeout = 10

    @ObjectBasedMetricMeasurement.measure_execution_metrics
    def _send_request(
        self,
        headers: dict,
        payload: dict,
        *,
        retry: int = 0,
        api_url=None,
        is_json=False,
        **kwargs,
    ) -> Optional[Dict]:

        data = dict(headers=headers, timeout=self.timeout, **kwargs)

        if is_json:
            data['json'] = payload
        else:
            data['data'] = payload

        try:
            response = requests.request(self.request_method, self.get_request_url(api_url), **data)
            response.raise_for_status()
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as ex:
            # Do not retry for 401 and 403 cases, also delete tokens
            if isinstance(ex, requests.HTTPError) and ex.response is not None and ex.response.status_code in (401, 403):
                if self.provider == 'toman':
                    from exchange.corporate_banking.integrations.toman.authenticator import CobankTomanAuthenticator

                    remove_tokens(
                        CobankTomanAuthenticator.access_token_settings_key,
                        CobankTomanAuthenticator.refresh_token_settings_key,
                    )
                elif self.provider == 'jibit':
                    from exchange.corporate_banking.integrations.jibit.authenticator import CobankJibitAuthenticator

                    remove_tokens(
                        CobankJibitAuthenticator.access_token_settings_key,
                        CobankJibitAuthenticator.refresh_token_settings_key,
                    )

                raise

            if retry > 0:
                return self._send_request(headers, payload, api_url=api_url, retry=retry - 1, is_json=is_json, **kwargs)

            raise

        return response.json()

    def get_request_url(self, api_url: Optional[str] = None):
        return self.base_url.format(api_url or self.api_url)
