import json
from abc import ABC, abstractmethod
from typing import Dict

import requests
from django.conf import settings

from exchange.asset_backed_credit.exceptions import InternalAPIError
from exchange.base.logging import metric_incr, report_event, report_exception

NOBITEX_BASE_URL = 'https://api.nobitex.ir' if settings.IS_PROD else 'https://testnetapi.nobitex.ir'


class AbstractBaseAPI(ABC):
    url: str
    method: str
    timeout: int = 30
    content_type: str = 'application/json'
    service_name: str
    endpoint_key: str

    def __init__(self):
        self.headers = {}
        self.response = None

    def _request(self, **kwargs):
        metric_name = self.get_metric_name()

        self.headers.update(kwargs.get('headers', {}))
        if self.content_type:
            self.headers.update({'Content-type': self.content_type})

        kwargs['headers'] = self.headers
        response = None
        try:
            response = requests.request(
                method=self.method,
                url=self.url,
                timeout=self.timeout,
                **kwargs,
            )
            self.response = response

            if not response.ok:
                report_event(f'InternalRequestError:{self.endpoint_key}', extras={'resp': response.json(), **kwargs})

            response.raise_for_status()
            self.validate_response(response)

        except (requests.Timeout, requests.exceptions.ConnectionError) as e:
            metric_incr(f'metric_abc_errors__{metric_name}_connection')
            raise InternalAPIError(e) from e
        except (requests.exceptions.RequestException, requests.exceptions.HTTPError, UnicodeDecodeError) as e:
            metric_incr(f'metric_abc_errors__{metric_name}_{response.status_code}')
            raise InternalAPIError(e) from e
        else:
            metric_incr(f'metric_abc_calls__{metric_name}')
            return response

    def get_metric_name(self):
        return self.service_name + '_' + self.endpoint_key

    @abstractmethod
    def request(self, *args, **kwargs):
        raise NotImplementedError

    @staticmethod
    def jsonify_request_data(request):
        return json.loads(request.body.decode('utf-8'))

    @staticmethod
    def jsonify_response_data(response):
        try:
            return response.json()
        except requests.JSONDecodeError:
            return {'body': response.text}

    def validate_response(self, response: requests.Response):
        metric_name = self.get_metric_name()
        try:
            response.json()
        except requests.exceptions.JSONDecodeError as e:
            metric_incr(f'metric_abc_errors__{metric_name}_{response.status_code}')
            report_exception()
            raise InternalAPIError('invalid response content-type text, expected json.') from e
        return response


class InternalAPI(AbstractBaseAPI):
    need_auth: bool

    def _get_auth_header(self) -> Dict:
        return {'Authorization': settings.ABC_INTERNAL_API_JWT_TOKEN}

    def _request(self, **kwargs):
        if self.need_auth:
            self.headers.update(self._get_auth_header())
        return super()._request(**kwargs)


class PublicAPI(AbstractBaseAPI):
    pass
