import logging
from typing import Optional, Tuple

import requests
from django.conf import settings
from django.utils.functional import cached_property
from requests import Timeout

from exchange.base.decorators import measure_time_cm
from exchange.base.logging import metric_incr, report_event
from exchange.base.models import Settings

logger = logging.getLogger(__name__)


class AutoKycRestWrapper:

    def __init__(self, timeout_seconds: float):
        self.headers = self._create_headers()
        self.timeout_seconds = timeout_seconds
        self.liveness_endpoint = '/authorization'

    def _create_headers(self) -> dict:
        return {
            'Accept': 'application/json',
            'Authorization': 'Bearer ' + self._get_jibit_verification_token()
        }

    @staticmethod
    def _get_jibit_verification_token() -> str:
        return settings.JIBIT_KYC_TOKEN

    def send_https_request(self, endpoint: str, data: dict, files: dict = None) -> Optional[Tuple[dict, int]]:
        endpoint_key = endpoint.replace("_", "").replace('/', '')
        with measure_time_cm(metric=f'auto_kyc_{endpoint_key}'):
            try:
                response = requests.post(
                    self.base_url + endpoint,
                    headers=self.headers, data=data, files=files, timeout=self.timeout_seconds)
            except Timeout as e:
                metric_incr(f'metric_integrations_errors__autokyc_{endpoint_key}_connection')
                raise e
            except Exception as e:
                report_event("Unexpected Exception occurred while trying to send data to AutoKyc.")
                raise e
            else:
                if response.status_code >= 400:
                    metric_incr(f'metric_integrations_errors__autokyc_{endpoint_key}_{response.status_code}')
                return response.json(), response.status_code
            finally:
                metric_incr(f'metric_integrations_calls__autokyc_{endpoint_key}')

    @cached_property
    def base_url(self):
        return Settings.get('auto_kyc_url', 'https://napi.jibit.ir/newalpha/api')

    def extract_auto_kyc_error_message(self, data: dict, status_code: int) -> Tuple[bool, str]:
        """
        Extract error message from alpha response
        """
        # Check response status
        has_error = False
        error_message = None
        error_code = '00'

        if status_code != 200:
            has_error = True
        if not has_error:
            if data.get("errorCode", None):
                error_code = data["errorCode"]
                has_error = True
            elif 'verification_result' not in data or 'liveness_result' not in data:
                has_error = True
            elif type(data.get('verification_result')) == dict and data.get('verification_result', {}).get('errorCode',
                                                                                                           None):
                error_code = data['verification_result']['errorCode']
                has_error = True
            elif type(data.get('liveness_result')) == dict and data.get('liveness_result', {}).get('errorCode', None):
                error_code = data['liveness_result']['errorCode']
                has_error = True
        if has_error:
            if data.get("errorMessage", None):
                error_message = data.get("errorMessage")
                error_details = data.get("data") or dict()
                if error_details and type(error_details) == dict:
                    errors = ""
                    for key, value in error_details.items():
                        errors += f'{key}: {value[0]},'
                    if errors:
                        error_message += f': {errors}'
                elif error_details:
                    error_message += f': {error_details}'
            elif data.get('verification_result', None) or data.get('liveness_result', None):
                if type(data.get('verification_result')) == dict and data.get('verification_result', {}).get(
                    'errorMessage'):
                    vr_error = data.get('verification_result', {}).get('errorMessage')
                    if vr_error:
                        error_message = vr_error
                elif type(data.get('liveness_result', None)) == dict and data.get('liveness_result', {}).get(
                    'errorMessage'):
                    lr_error = data.get('liveness_result', {}).get('errorMessage')
                    if lr_error:
                        error_message = lr_error
            if not error_message:
                error_message = f'پاسخ مناسبی از سرور دریافت نشد - {data}'

            endpoint_key = self.liveness_endpoint.replace("_", "").replace('/', '')
            metric_incr(f'metric_integrations_errors__autokyc_{endpoint_key}_{error_code}')
        return has_error, error_message

    def extract_auto_kyc_results(self, data: dict) -> Tuple[bool, bool]:
        """
        extract verification_result and liveness result from api_response.json (alpha response)
        it supports alpha apis version 1 and 2
        """
        from exchange.base.parsers import parse_bool
        # Call successful, check verification status
        vr_result = data.get('verification_result', dict())
        if type(vr_result) == dict:
            vr_data = vr_result.get("data", dict())
            verification_result = parse_bool(vr_data.get("result", False))
        else:
            verification_result = parse_bool(vr_result)

        lr_result = data.get('liveness_result', dict())
        if type(lr_result) == dict:
            lr_data = lr_result.get("data", dict())
            liveness_result = parse_bool(lr_data.get("State", False))
        else:
            liveness_result = parse_bool(lr_result)

        return verification_result, liveness_result
