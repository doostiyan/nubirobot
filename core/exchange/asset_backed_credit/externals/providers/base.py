import json
from typing import TYPE_CHECKING, Dict, Optional

import requests
from django.conf import settings
from django_redis import get_redis_connection
from rest_framework.renderers import JSONRenderer

from exchange.asset_backed_credit.constant import API_LOG_CACHE_KEY
from exchange.asset_backed_credit.exceptions import ClientError, ThirdPartyError
from exchange.asset_backed_credit.models import OutgoingAPICallLog, UserService
from exchange.base.calendar import ir_now
from exchange.base.cryptography.rsa import RSASigner
from exchange.base.logging import metric_incr, report_exception
from exchange.base.scrubber import scrub

if TYPE_CHECKING:
    from exchange.asset_backed_credit.services.providers.provider import Provider


class ProviderAPI:
    provider: 'Provider'
    url: str
    endpoint_key: str
    method: str
    need_auth: bool
    max_retry: int = 1
    timeout: int = 30
    content_type: str
    raise_for_status: bool = True

    def _get_auth_header(self) -> Dict:
        raise NotImplementedError()

    def __init__(self, user_service: Optional[UserService] = None) -> None:
        self.user_service = user_service
        self.api_log = OutgoingAPICallLog(
            provider=self.provider.id,
            service=(self.user_service.service.tp if self.user_service else None),
            user_service=self.user_service,
            api_url=self.url,
            retry=-1,
            user_id=(self.user_service.user_id if self.user_service else None),
        )

    def _update_api_call_log(self, response: requests.Response, *args, **kwargs):
        self.api_log.request_body = scrub(self.jsonify_request_data(response.request))
        self.api_log.response_body = scrub(self.jsonify_response_data(response))

        self.api_log.response_code = response.status_code
        self.api_log.status = (
            OutgoingAPICallLog.STATUS.success if response.status_code == 200 else OutgoingAPICallLog.STATUS.failure
        )
        self.api_log.retry += 1
        self.api_log.created_at = ir_now()

    def _save_api_call_log(self):
        from exchange.asset_backed_credit.api.serializers import OutgoingAPICallLogSerializer

        if self.api_log:
            data_json = JSONRenderer().render(OutgoingAPICallLogSerializer(self.api_log).data)
            cache = get_redis_connection('default')
            cache.rpush(API_LOG_CACHE_KEY, data_json)

    def renew_token(self) -> Optional[str]:
        raise NotImplementedError()

    def _save_api_log_in_connection_failed(self):
        self.api_log.response_code = 522
        self.api_log.status = OutgoingAPICallLog.STATUS.failure
        self._save_api_call_log()

    def _retry(self, **kwargs):
        self.api_log.retry += 1
        if self.api_log.retry >= self.max_retry:
            self._save_api_log_in_connection_failed()
            report_exception()
            raise ValueError(f'{self.endpoint_key}Error: Connection error')
        return self._request(**kwargs)

    def _request(self, **kwargs):
        # create metric name
        metric_name = self.provider.name + '_' + self.endpoint_key

        # update headers
        headers = kwargs.get('headers', {})
        # add content-type to headers
        if self.content_type:
            headers.update({'Content-type': self.content_type})
        # add auth to headers
        if self.need_auth:
            headers.update(self._get_auth_header())

        kwargs['headers'] = headers
        response = None
        try:
            response = requests.request(
                method=self.method,
                url=self.url,
                timeout=self.timeout,
                hooks={'response': [self._update_api_call_log]},
                **kwargs,
            )
            # token dose not exist or expired
            if self.need_auth and response.status_code == 401:
                token = self.renew_token()
                kwargs['headers']['Authorization'] = token
                response = requests.request(
                    self.method,
                    self.url,
                    timeout=self.timeout,
                    hooks={'response': [self._update_api_call_log]},
                    **kwargs,
                )
            self._save_api_call_log()

            # check response status
            if self.raise_for_status:
                response.raise_for_status()

            self.validate_response(response)

        except (requests.Timeout, requests.exceptions.ConnectionError) as e:
            metric_incr(f'metric_abc_errors__{metric_name}_connection')
            return self._retry(**kwargs)

        except (requests.exceptions.RequestException, requests.exceptions.HTTPError, UnicodeDecodeError) as e:
            metric_incr(f'metric_abc_errors__{metric_name}_{response.status_code}')
            report_exception()
            raise ClientError(e) from e
        else:
            metric_incr(f'metric_abc_calls__{metric_name}')
            return response

    def request(self, *args, **kwargs):
        raise NotImplementedError

    @staticmethod
    def jsonify_request_data(request):
        if request.body is not None:
            return json.loads(request.body.decode('utf-8'))
        return {}

    @staticmethod
    def jsonify_response_data(response):
        try:
            return response.json()
        except requests.JSONDecodeError:
            return {'body': response.text}

    def validate_response(self, response: requests.Response):
        metric_name = self.provider.name + '_' + self.endpoint_key
        try:
            response.json()
        except requests.exceptions.JSONDecodeError as e:
            metric_incr(f'metric_abc_errors__{metric_name}_{response.status_code}')
            report_exception()
            raise ThirdPartyError('invalid response content-type text, expected json.') from e
        return response

    @classmethod
    def sign(cls, data: str):
        """
        Signs a data string by RSASigner with and ABC_PRIVATE_KEY returns the base64-encoded signature.
        Params:
            data (str): the string that wants to sign.
        """
        signer = RSASigner(settings.ABC_PRIVATE_KEY)

        return signer.sign(data)
