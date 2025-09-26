import base64
import enum
import hashlib
import hmac
import time
import typing
from json import JSONDecodeError

import requests
from django.conf import settings
from requests import PreparedRequest

from exchange.base.decorators import measure_time_cm
from exchange.base.logging import metric_incr, report_event
from exchange.base.models import Settings


class Client:
    BASE_URLS = settings.XCHANGE_MARKET_MAKER_BASE_URLS
    TIMEOUT = 5
    API_SECRET = settings.XCHANGE_MARKET_MAKER_SECRET
    HEADERS = {
        'content-type': 'application/json',
        'mm-apikey': settings.XCHANGE_MARKET_MAKER_API_KEY,
        'mm-sign': 'sign',
        'user-agent': f'Nobitex/{settings.RELEASE_VERSION}.{settings.CURRENT_COMMIT}',
    }

    class Method(enum.Enum):
        GET = 'GET'
        POST = 'POST'

    @classmethod
    def request(
        cls,
        method: Method,
        path: str,
        data: typing.Optional[dict] = None,
        verbose: bool = False,
        query_params: typing.Optional[dict] = None,
    ) -> dict:
        server, url = cls.get_base_url()
        request = requests.Request(
            method=method.value,
            url=url + path,
            json=data,
            headers=cls.HEADERS,
            params=query_params,
        )
        session = requests.Session()
        signed_request = cls.sign(session, request)
        if verbose:
            print(f'sending request {signed_request.url}')

        with measure_time_cm(f'metric_convert_marketmaker_services_time__{server}_{path.replace("/", "")}'):
            response = session.send(signed_request, timeout=cls.TIMEOUT)
        if verbose:
            if response.status_code != 200 or response.json().get('hasError'):
                print(
                    f'Error in calling {signed_request.url} with headers {signed_request.headers}, received response with status code={response.status_code} and json={response.json()}'
                )
            else:
                result = response.json().get('result')
                if isinstance(result, list):
                    result = result[0] if len(result) > 0 else {}
                additional_info = (
                    result.get('baseToQuotePriceBuy') if 'baseToQuotePriceBuy' in result else result.get('quoteId')
                )
                print(
                    f'Successfully called {signed_request.url}, example result: {result.get("baseCurrency")}{result.get("quoteCurrency")}: {additional_info}'
                )

        # TODO: Remove after successful launch
        if response.status_code != 200 or response.json().get('hasError'):
            report_event(
                'market_maker_api_error',
                extras={
                    'url': signed_request.url,
                    'status_code': response.status_code,
                    'body': response.json(),
                },
            )
        cls.log_count_metric(response, server, path)
        return response.json()

    @classmethod
    def log_count_metric(cls, response, server, path) -> None:
        result = 'success'
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            try:
                result = err.response.json()['error']
            except (KeyError, ValueError, JSONDecodeError):
                result = 'HTTPError'
            raise
        except requests.exceptions.Timeout:
            result = 'timeout'
            raise
        except (requests.exceptions.RequestException, Exception) as err:
            result = err.__class__.__name__
            raise
        finally:
            result = result.replace("_", "").replace(" ", "").lower()
            metric_incr(f'metric_convert_marketmaker_services__{server}_{path.replace("/", "")}_{result}')

    @classmethod
    def sign(cls, session: requests.Session, request: requests.Request) -> PreparedRequest:
        request = session.prepare_request(request)
        timestamp = str(int(time.time() * 1000))
        if request.method == cls.Method.GET.value and '?' in request.url:
            request.url += f'&timestamp={timestamp}'
        else:
            request.url += f'?timestamp={timestamp}'

        signable_payload: str = request.url.split('?')[1]
        if request.body:
            signable_payload += request.body.decode().replace(' ', '')
        request.headers['mm-sign'] = base64.b64encode(
            hmac.new(
                key=cls.API_SECRET.encode(),
                msg=signable_payload.encode(),
                digestmod=hashlib.sha256,
            ).digest(),
        ).decode()
        return request

    @classmethod
    def get_base_url(cls) -> (str, str):
        default = 'direct'
        value = Settings.get('market_maker_convert_services_url', default)
        try:
            return value, cls.BASE_URLS[value]
        except KeyError as e:
            return default, cls.BASE_URLS.get(default)
