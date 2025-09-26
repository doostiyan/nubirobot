import base64
import hashlib
import hmac
import json
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from exchange.base.logging import metric_incr, report_exception
from exchange.base.models import Settings
from exchange.liquidator.errors import BrokerAPIError, BrokerAPIError4XX

BASE_URLS = settings.LIQUIDATOR_MARKET_MAKER_BASE_URLS

LIMIT_FAILURE_RATE = 10
LIMIT_FAILURE_TIME = 5 * 60
DEACTIVATE_API_TIME = 5 * 60


class BrokerBaseAPI:
    url: str
    method: str
    timeout: int = 5
    metric_name: str
    retry_limit: int = 0
    activity_status_cache_key = 'liquidator_is_broker_active'
    failure_rate_cache_key = 'liquidator_broker_failure_rate'

    @staticmethod
    def get_base_url() -> str:
        default = 'direct'
        value = Settings.get('market_maker_settlement_service_base_url', default)
        try:
            return BASE_URLS[value]
        except KeyError:
            return BASE_URLS.get(default)

    @classmethod
    def generate_sign(cls, params: dict, body: dict):
        payload = urlencode(params)
        if body:
            payload += json.dumps(body).replace(' ', '')

        sign = base64.b64encode(
            hmac.new(
                key=settings.LIQUIDATOR_MARKET_MAKER_SECRET.encode(),
                msg=payload.encode(),
                digestmod=hashlib.sha256,
            ).digest(),
        ).decode()

        return sign

    def _request(self, retry: int = 0, **kwargs):
        # update headers
        headers = kwargs.get('headers', {})
        params = kwargs.get('params', {})
        body = kwargs.get('json', {}) or kwargs.pop('data', {})

        params['timestamp'] = timezone.now().timestamp()
        sign = self.generate_sign(params, body)

        headers.update(
            {
                'Content-type': 'application/json',
                'MM-SIGN': sign,
                'MM-APIKEY': settings.LIQUIDATOR_MARKET_MAKER_API_KEY,
            }
        )

        kwargs['headers'] = headers
        kwargs['params'] = params
        kwargs['json'] = body

        response = None
        try:
            response = requests.request(
                method=self.method,
                url=self.get_base_url() + self.url,
                timeout=self.timeout,
                **kwargs,
            )
            response.raise_for_status()
        except (requests.Timeout, requests.exceptions.ConnectionError):
            metric_incr(f'metric_liquidator_external_market_errors__{self.metric_name}_connection')
            self.log_failure()
            return self._retry(retry=retry + 1, message_error='connection error', **kwargs)

        except requests.exceptions.HTTPError as e:
            metric_incr(f'metric_liquidator_external_market_errors__{self.metric_name}_{response.status_code}')
            self.log_failure()
            report_exception()

            if response.status_code and response.status_code < 500:
                try:
                    json_response = response.json()
                    message = json_response.get('error', '') if json_response.get('hasError', True) else ''
                except json.decoder.JSONDecodeError:
                    message = ''
            else:
                return self._retry(retry=retry + 1, message_error=str(e), **kwargs)
            raise BrokerAPIError4XX(message) from e

        except (requests.exceptions.RequestException, UnicodeDecodeError) as e:
            status_code = response.status_code if hasattr('response', 'status_code') else 500
            metric_incr(f'metric_liquidator_external_market_errors__{self.metric_name}_{status_code}')
            self.log_failure()
            report_exception()
            return self._retry(retry=retry + 1, message_error=str(e), **kwargs)
        else:
            metric_incr(f'metric_liquidator_external_market_calls__{self.metric_name}')

        json_response = response.json()
        if json_response.get('hasError', False):
            self.log_failure()
            raise BrokerAPIError(json_response.get('error', ''))
        return json_response.get('result', {})

    def _retry(self, retry: int, message_error: str = '', **kwargs):
        if retry < self.retry_limit:
            return self._request(retry=retry + 1, **kwargs)
        raise BrokerAPIError(message_error)

    @classmethod
    def log_failure(cls):
        failure_number = cache.get(cls.failure_rate_cache_key)

        if failure_number:
            if failure_number > LIMIT_FAILURE_RATE:
                cls.deactivate_broker()
            cache.incr(cls.failure_rate_cache_key)
            return

        cache.set(cls.failure_rate_cache_key, 1, timeout=LIMIT_FAILURE_TIME)

    @classmethod
    def is_failure_limit_reached(cls):
        return cache.get(cls.failure_rate_cache_key, 0) > LIMIT_FAILURE_RATE

    @classmethod
    def is_active(cls):
        return cache.get(cls.activity_status_cache_key, 'yes') == 'yes'

    @classmethod
    def deactivate_broker(cls, *, for_limited_time=True):
        timeout = DEACTIVATE_API_TIME if for_limited_time else None
        cache.set(cls.activity_status_cache_key, 'no', timeout=timeout)

    @classmethod
    def activate_broker(cls):
        cache.set(cls.activity_status_cache_key, 'yes')
