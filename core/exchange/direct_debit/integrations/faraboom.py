import datetime
import decimal
import json
import time
from functools import cached_property
from typing import Optional

import pytz
import requests
from django.core.cache import cache
from django.urls import reverse
from requests import JSONDecodeError, RequestException

from exchange import settings
from exchange.base.calendar import ir_now
from exchange.base.decorators import measure_time_cm
from exchange.base.helpers import get_base_api_url
from exchange.base.logging import metric_incr, report_exception
from exchange.base.models import Settings
from exchange.base.parsers import parse_int
from exchange.direct_debit.constants import PAGE_SIZE_IN_FETCH_DEPOSITS
from exchange.direct_debit.exceptions import (
    ThirdPartyAuthenticatorError,
    ThirdPartyConnectionError,
    ThirdPartyUnavailableError,
)
from exchange.direct_debit.types import DirectDebitAuthData


class FaraboomAPIMixins:
    provider = 'faraboom'
    @cached_property
    def base_url(self):
        return (
            settings.FARABOOM_APIS_BASE_URL
            if settings.IS_PROD
            else Settings.get_value('direct_debit_testnet_base_url', 'https://payman2.sandbox.faraboom.co')
        )


class FaraboomAuthenticator(FaraboomAPIMixins):
    access_token_cache_name = 'direct_debit_access_token'
    endpoint = '/oauth/token'
    metric_name = f'login_{endpoint}'

    def __init__(self):
        self.is_available = True
        self.last_checked = 0
        self.check_interval = 5
        self.failure_threshold = 3
        self.failure_count = 0

    def check_availability(self):
        if time.time() - self.last_checked > self.check_interval:
            try:
                response = requests.head(self.base_url, timeout=5)
                if response.status_code == 200:
                    self.is_available = True
                    self.failure_count = 0
                else:
                    self.failure_count += 1
                    if self.failure_count >= self.failure_threshold:
                        self.is_available = False
            except requests.RequestException:
                self.failure_count += 1
                if self.failure_count >= self.failure_threshold:
                    self.is_available = False

            self.last_checked = time.time()

    @property
    def access_token(self):
        return cache.get(self.access_token_cache_name) or self.acquire_access_token()

    def acquire_access_token(self) -> str:
        response = None
        access_token = None

        self.check_availability()
        if not self.is_available:
            raise ThirdPartyUnavailableError('Third party service is currently unavailable.')

        try:
            auth_data = self.get_faraboom_auth_data()
            data = {
                'client_id': auth_data.client_id,
                'client_secret': auth_data.client_secret,
                'grant_type': 'client_credentials',
            }
            with measure_time_cm(metric=f'direct_debit_provider_time__{self.provider}_auth_bank'):
                response = requests.post(url=f'{self.base_url}{self.endpoint}', data=data, timeout=30)
            response.raise_for_status()

            if response.status_code == 200:
                json_response = response.json()
                access_token = json_response.get('access_token')
                expires_in = parse_int(json_response.get('expires_in')) or (5 * 60 * 60)
                cache.set(self.access_token_cache_name, access_token, expires_in)
        except (requests.Timeout, requests.ConnectionError) as e:
            metric_incr(f'metric_direct_debit_provider_calls__{self.provider}_auth_bank_ConnectionError')
            raise ThirdPartyConnectionError from e
        except RequestException as e:
            if response is not None and response.status_code:
                metric_incr(
                    f'metric_direct_debit_provider_calls__{self.provider}_auth_bank_Request{response.status_code}'
                )
            else:
                metric_incr(f'metric_direct_debit_provider_calls__{self.provider}_auth_bank_RequestError')
            raise ThirdPartyAuthenticatorError from e
        else:
            metric_incr(f'metric_direct_debit_provider_calls__{self.provider}_auth_bank_Successful')
            return access_token

    def get_faraboom_auth_data(self) -> DirectDebitAuthData:
        client_id = (
            settings.DIRECT_DEBIT_CLIENT_ID
            if settings.IS_PROD
            else Settings.get_value('direct_debit_testnet_client_id', 'nobitex')
        )
        client_secret = (
            settings.DIRECT_DEBIT_CLIENT_SECRET
            if settings.IS_PROD
            else Settings.get_value('direct_debit_testnet_client_secret', 'a_8_D85A')
        )
        app_key = (
            settings.FARABOOM_APP_KEY
            if settings.IS_PROD
            else Settings.get_value('direct_debit_testnet_app_key', 'nobitex')
        )
        return DirectDebitAuthData(
            client_id=client_id,
            client_secret=client_secret,
            app_key=app_key,
        )


class FaraboomClient(FaraboomAPIMixins):
    authenticator = FaraboomAuthenticator()
    timeout = 30
    app_key = settings.FARABOOM_APP_KEY

    @property
    def _headers(self):
        # These parameters should be removed. so we put fixed params
        return {
            'app-key': self.app_key,
            'Client-Ip-Address': '127.0.0.1',
            'Client-Platform-Type': 'web',
            'Client-Device-Id': '169.254.75.178',
            'Client-User-Id': '09351234567',
            'Client-User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Authorization': f'Bearer {self.authenticator.access_token}',
            'Content-Type': 'application/json',
        }

    def _update_request_header(self, _kwargs):
        _kwargs.get('headers', {}).update(self._headers)
        if not _kwargs.get('headers'):
            _kwargs['headers'] = self._headers
        return _kwargs

    def request(self, endpoint, method, **kwargs):
        response = None
        url = f'{self.base_url}{endpoint}'
        timeout = kwargs.pop('timeout', self.timeout)
        metric_name = kwargs.pop('metric_name')
        bank_id = kwargs.pop('bank_id')

        kwargs = self._update_request_header(kwargs)

        try:
            with measure_time_cm(metric=f'direct_debit_provider_time__{self.provider}_{metric_name}_{bank_id}'):
                response = requests.request(method, url, timeout=timeout, **kwargs, allow_redirects=False)
            if response.status_code == 401:
                self.authenticator.acquire_access_token()
                kwargs = self._update_request_header(kwargs)
                with measure_time_cm(metric=f'direct_debit_provider_time__{self.provider}_{metric_name}_{bank_id}'):
                    response = requests.request(method, url, timeout=timeout, **kwargs)

            response.raise_for_status()

        except (requests.Timeout, requests.ConnectionError, ThirdPartyUnavailableError) as e:
            metric_incr(f'metric_direct_debit_provider_calls__{self.provider}_{metric_name}_{bank_id}_ConnectionError')
            raise ThirdPartyConnectionError from e
        except RequestException:
            if response is not None:
                try:
                    error_code = response.json().get('code', 'Error')
                except JSONDecodeError:
                    error_code = response.status_code

                metric_incr(
                    f'metric_direct_debit_provider_calls__{self.provider}_{metric_name}_{bank_id}_Request{error_code}'
                )
            else:
                metric_incr(f'metric_direct_debit_provider_calls__{self.provider}_{metric_name}_{bank_id}_RequestError')
            raise

        metric_incr(f'metric_direct_debit_provider_calls__{self.provider}_{metric_name}_{bank_id}_Successful')
        return response


class FaraboomHandler:
    client = FaraboomClient()

    @staticmethod
    def _get_create_contract_callback_url(trace_id: str) -> str:
        return (
            f'{get_base_api_url(trailing_slash=False)}'
            f'{reverse(viewname="create_contract_callback", kwargs={"trace_id": trace_id})}'
        )

    @staticmethod
    def _get_update_contract_callback_url(trace_id: str) -> str:
        return (
            f'{get_base_api_url(trailing_slash=False)}'
            f'{reverse(viewname="update_contract_callback", kwargs={"trace_id": trace_id})}'
        )

    @classmethod
    def create_contract(cls, contract: 'DirectDebitContract'):
        endpoint = '/v1/payman/create'
        user = contract.user
        headers = {
            'Mobile-no': user.mobile,
            'National-code': user.national_code,
        }
        payload = json.dumps(
            {
                'payman': {
                    'bank_code': contract.bank.bank_id,
                    'user_id': contract.user_code,
                    'permission_ids': [
                        1,
                    ],
                    'contract': {
                        'max_daily_transaction_count': str(contract.daily_max_transaction_count),
                        'max_monthly_transaction_count': str(contract.daily_max_transaction_count * 31),
                        'max_transaction_amount': str(contract.max_transaction_amount),
                        'start_date': contract.started_at.isoformat(),
                        'expiration_date': contract.expires_at.isoformat(),
                    },
                },
                'redirect_url': cls._get_create_contract_callback_url(contract.trace_id),
                'trace_id': contract.trace_id,
            },
        )

        metric_name = 'CreateContract'
        return cls.client.request(
            endpoint=endpoint,
            method='POST',
            data=payload,
            headers=headers,
            metric_name=metric_name,
            bank_id=contract.bank.bank_id,
        )

    @classmethod
    def update_contract(cls, contract: 'DirectDebitContract'):
        endpoint = '/v1/payman/update'
        user = contract.user
        headers = {
            'Mobile-no': user.mobile,
            'National-code': user.national_code,
        }
        payload = json.dumps(
            {
                'payman_id': contract.contract_id,
                'expiration_date': contract.expires_at.isoformat(),
                'max_daily_transaction_count': str(int(contract.daily_max_transaction_count)),
                'max_transaction_amount': str(int(contract.max_transaction_amount)),
                'redirect_url': cls._get_update_contract_callback_url(contract.trace_id),
            }
        )

        metric_name = 'UpdateContract'
        return cls.client.request(
            endpoint=endpoint,
            method='POST',
            data=payload,
            headers=headers,
            metric_name=metric_name,
            bank_id=contract.bank.bank_id,
        )

    @classmethod
    def activate_contract(cls, contract_code: str, bank_id: str):
        endpoint = f'/v1/payman/getId?payman_code={contract_code}'
        metric_name = 'ActiveContract'
        return cls.client.request(
            endpoint=endpoint,
            method='GET',
            metric_name=metric_name,
            bank_id=bank_id,
        )

    @classmethod
    def direct_deposit(
        cls,
        trace_id: str,
        contract_id: str,
        amount: decimal.Decimal,
        bank_id: str,
        description: Optional[str] = None,
    ):
        endpoint = '/v1/payman/pay'
        data = {
            'trace_id': trace_id,
            'payman_id': contract_id,
            'amount': str(amount),
            'description': description,
            'client_transaction_date': ir_now().strftime('%Y-%m-%dT%H:%M:%SZ'),
        }
        return cls.client.request(
            endpoint=endpoint, method='POST', data=json.dumps(data), metric_name='DirectDeposit', bank_id=bank_id
        )

    @classmethod
    def change_contract_status(cls, contract_id: str, new_status: str, bank_id: str):
        endpoint = '/v1/payman/status/change'
        metric_name = 'ChangeContractStatus'
        payload = json.dumps(
            {
                'payman_id': contract_id,
                'new_status': new_status,
            }
        )
        return cls.client.request(
            endpoint=endpoint,
            method='POST',
            data=payload,
            metric_name=metric_name,
            bank_id=bank_id,
        )

    @classmethod
    def fetch_deposits(
        cls,
        from_date: datetime,
        to_date: datetime,
        page: int,
        page_size: int = PAGE_SIZE_IN_FETCH_DEPOSITS,
        only_banks=None,
    ):
        from exchange.direct_debit.models import DirectDebitBank

        endpoint = '/v1/reports/transactions'
        page = page if page > 0 else 1
        responses = []
        page_size = page_size if page_size > 0 else PAGE_SIZE_IN_FETCH_DEPOSITS
        banks = DirectDebitBank.objects.all()
        tehran_from_date = from_date.astimezone(pytz.timezone('Asia/Tehran')).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        tehran_to_date = to_date.astimezone(pytz.timezone('Asia/Tehran')).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        retires = 0
        skip_banks = Settings.get_cached_json(
            'direct_deposit_skip_banks_sync',
            [
                'MELIIR',
                'BLUBIR',
            ],
        )

        for bank in banks:
            if bank.bank_id in skip_banks or (only_banks is not None and bank.bank_id not in only_banks):
                continue

            while retires < 5:
                try:
                    params = {
                        'offset': (page - 1) * page_size,  # convert page to offset
                        'length': page_size,
                        'start_date': tehran_from_date,
                        'end_date': tehran_to_date,
                        'bank_code': bank.bank_id,
                    }
                    _response = (
                        cls.client.request(
                            endpoint=endpoint,
                            method='POST',
                            data=json.dumps(params),
                            metric_name='FetchDeposits',
                            bank_id=bank.bank_id,
                            timeout=60,
                        ).json()
                        or []
                    )
                    responses.extend(_response)
                    break
                except:
                    retires += 1
                    if settings.IS_PROD:
                        report_exception()
            else:
                raise ThirdPartyConnectionError()

        return responses

    @classmethod
    def fetch_deposit_stats(cls, trace_id: str, date: datetime, bank_id: str):
        """
        sample response:
        {
          "currency": "IRR",
          "description": "Nobitex Direct Debit Transaction",
          "destination_bank": "SINAIR",
          "destination_deposit": "361-813-2295556-1",
          "source_bank": "SINAIR",
          "source_deposit": "119-813-2295556-1",
          "transaction_type": "NORMAL",
          "reference_id": "00001735566162618055",
          "trace_id": "55bae6e361584c678f78f7e19a6db842",
          "transaction_amount": 9900000,
          "transaction_time": 1735566159000,
          "batch_id": 1337466,
          "commission_amount": 0,
          "status": "SUCCEED",
          "is_over_draft": false
        }
        """
        date = date.astimezone(pytz.timezone('Asia/Tehran')).date()
        endpoint = f'/v1/payman/pay/trace?trace-id={trace_id}&date={date.isoformat()}'
        metric_name = 'FetchDepositStats'
        return cls.client.request(
            endpoint=endpoint,
            method='GET',
            metric_name=metric_name,
            bank_id=bank_id,
        )
