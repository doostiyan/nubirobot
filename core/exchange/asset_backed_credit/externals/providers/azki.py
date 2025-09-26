from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Union
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.core.cache import cache
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from exchange.asset_backed_credit.exceptions import ClientError, ThirdPartyError
from exchange.asset_backed_credit.externals.providers.base import ProviderAPI
from exchange.asset_backed_credit.models import Service, UserService
from exchange.asset_backed_credit.services.providers.provider import SignSupportProvider
from exchange.asset_backed_credit.types import (
    ProviderBasedLoanCalculationData,
    ProviderFeeType,
    UserServiceCreateRequest,
)
from exchange.base.decorators import measure_time_cm
from exchange.base.logging import report_event

AZKI_BASE_URL = 'https://service.azkivam.com' if settings.IS_PROD else 'https://service.azkiloan.com'


@dataclass
class AzkiProvider(SignSupportProvider):
    contract_id: str
    username: str
    password: str


AZKI = AzkiProvider(
    name='azki',
    ips=(['94.182.153.147'] if settings.IS_PROD else ['78.38.246.150', '94.182.196.158']),
    pub_key='' if settings.IS_PROD else '',
    id=Service.PROVIDERS.azki,
    contract_id=settings.ABC_AZKI_FINANCIER_ID,
    account_id=(10900034 if settings.IS_PROD else 332716 if settings.IS_TESTNET else -1),
    username=settings.ABC_AZKI_USERNAME,
    password=settings.ABC_AZKI_PASSWORD,
)


class AzkiAPI(ProviderAPI):
    provider = AZKI
    error_message = None
    content_type = None

    SUCCESS_STATUS = 0


class AzkiRenewTokenAPI(AzkiAPI):
    url = f'{AZKI_BASE_URL}/auth/login'
    endpoint_key = 'renewToken'
    method = 'POST'
    need_auth = False
    error_message = 'AzkiRenewToken'
    max_retry = 3
    content_type = 'application/json'

    @measure_time_cm(metric='azki_renewToken')
    def request(self):
        try:
            resp = self._request(
                json={
                    'username': self.provider.username,
                    'password': self.provider.password,
                }
            )
        except (ValueError, ClientError) as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        data = resp.json()
        if not data.get('rsCode') == self.SUCCESS_STATUS:
            raise ThirdPartyError(f'{self.error_message}: invalid response, rsCode error.')

        access_token = data.get('result', {}).get('token')
        if not access_token:
            raise ThirdPartyError(f'{self.error_message}: invalid response, missing access_token')

        self.provider.set_token(access_token)
        return access_token


class AzkiWithAuthAPI(AzkiAPI):
    need_auth = True

    def _get_auth_header(self) -> Dict:
        token = self.provider.get_token()
        if not token:
            token = self.renew_token()
        return {'Authorization': 'Bearer ' + token}

    def renew_token(self):
        return AzkiRenewTokenAPI(self.user_service).request()


class ResultSchema(BaseModel):
    request_id: int
    credit_account_id: int
    coupon_book_id: int


class CreateResponseSchema(BaseModel):
    rs_code: int
    result: Union[int, ResultSchema]

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class AzkiCreateAccountAPI(AzkiWithAuthAPI):
    url = f'{AZKI_BASE_URL}/crypto-exchange/request-credit'
    method = 'POST'
    content_type = 'application/json'
    endpoint_key = 'createAccount'
    error_message = 'AzkiCreateAccount'
    raise_for_status = False

    SUCCESS_RS_CODE = 0

    def __init__(self, user_service: UserService, request_data: UserServiceCreateRequest):
        super().__init__(user_service)
        self.request_data = request_data

    @measure_time_cm(metric='azki_createAccount')
    def request(self) -> CreateResponseSchema:
        try:
            resp = self._request(json=self._get_request_body())
        except (ValueError, ClientError) as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        try:
            result = CreateResponseSchema(**resp.json())
        except ValidationError as e:
            report_event(f'{self.error_message}: result error', extras={'result': resp.json()})
            raise ThirdPartyError() from e

        if result.rs_code == 0 and not isinstance(result.result, ResultSchema):
            report_event(f'{self.error_message}: result error', extras={'result': resp.json()})
            raise ThirdPartyError()

        return result

    def _get_request_body(self):
        return {
            'user': {
                'first_name': self.request_data.user_info.first_name,
                'last_name': self.request_data.user_info.last_name,
                'mobile_number': self.request_data.user_info.mobile,
                'national_code': self.request_data.user_info.national_code,
            },
            'financier_id': self.provider.contract_id,
            'amount': self.request_data.amount,
            'period': self.request_data.period,
        }


class CalculatorSchema(BaseModel):
    name: str
    logo_url: str
    interest_rate: Decimal
    monthly_amount: int
    fee_rate: Decimal
    fee_amount: int
    sum_of_amounts: int
    loan_amount: int
    repayment_model: str
    period: int

    model_config = ConfigDict(
        alias_generator=to_camel,
    )


class AzkiCalculatorAPI(AzkiWithAuthAPI):
    url = f'{AZKI_BASE_URL}/crypto-exchange/plans'
    method = 'GET'
    endpoint_key = 'calculator'
    error_message = 'AzkiCalculator'
    content_type = None

    CACHE_KEY_FORMAT = 'abc:provider:azki:calculator:{principal}:{period}'
    CACHE_TIMEOUT = 5 * 60

    def __init__(self, principal: int, period: int):
        super().__init__()
        self.principal = principal
        self.period = period

    @measure_time_cm(metric='azki_calculator')
    def request(self):
        response_data = self._get_cached_response()
        if not response_data:
            try:
                resp = self._request(params={'amount': int(self.principal), 'period': self.period})
            except (ValueError, ClientError) as e:
                report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
                raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

            response_data = resp.json()
            if not response_data.get('rsCode') == self.SUCCESS_STATUS:
                raise ThirdPartyError(f'{self.error_message}: invalid response, rsCode error.')

            plans_data: List[Dict] = response_data.get('result', [])
            plans = []
            for plan in plans_data:
                try:
                    plans.append(CalculatorSchema(**plan))
                except ValidationError:
                    continue

            if not plans:
                report_event(f'{self.error_message}: request exception', extras={'plans': plans_data})
                raise ThirdPartyError(f'{self.error_message}: invalid response schema, no valid plan.')

            self._set_cached_response(result=response_data)

        return self._get_calculator_data(data=response_data)

    def _get_calculator_data(self, data):
        plans = [CalculatorSchema(**plan) for plan in data['result']]
        selected_plan = sorted(plans, key=lambda p: p.sum_of_amounts)[0]

        installment_amount = selected_plan.monthly_amount
        provider_fee_amount = selected_plan.fee_amount
        total_installments_amount = selected_plan.sum_of_amounts - provider_fee_amount

        return ProviderBasedLoanCalculationData(
            principal=self.principal,
            period=self.period,
            interest_rate=selected_plan.interest_rate,
            provider_fee_percent=selected_plan.fee_rate,
            provider_fee_amount=provider_fee_amount,
            provider_fee_type=ProviderFeeType.PRE_PAID,
            installment_amount=installment_amount,
            total_installments_amount=total_installments_amount,
            extra_info={
                'name': selected_plan.name,
                'repaymentModel': selected_plan.repayment_model,
            },
        )

    def _get_cached_response(self):
        key = self.CACHE_KEY_FORMAT.format(principal=self.principal, period=self.period)
        return cache.get(key)

    def _set_cached_response(self, result):
        key = self.CACHE_KEY_FORMAT.format(principal=self.principal, period=self.period)
        cache.set(key, result, timeout=self.CACHE_TIMEOUT)

    @staticmethod
    def jsonify_request_data(request):
        return parse_qs(urlparse(request.url).query)


class Options(BaseModel):
    minimum_finance: int
    maximum_finance: int
    periods: List[int]

    model_config = ConfigDict(
        alias_generator=to_camel,
    )


class AzkiServiceOptionsAPI(AzkiWithAuthAPI):
    url = f'{AZKI_BASE_URL}/crypto-exchange/summary'
    method = 'GET'
    content_type = 'application/json'
    endpoint_key = 'getOptions'
    error_message = 'AzkiGetOptions'

    @measure_time_cm(metric='azki_getOptions')
    def request(self):
        try:
            resp = self._request()
        except (ValueError, ClientError) as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        data = resp.json()
        if not data.get('rsCode') == self.SUCCESS_STATUS:
            report_event(f'{self.error_message}: result error', extras={'result': resp.json()})
            raise ThirdPartyError(f'{self.error_message}: request exception. invalid response')

        result = data.get('result')
        if not result:
            report_event(f'{self.error_message}: result error', extras={'result': resp.json()})
            raise ThirdPartyError(f'{self.error_message}: request exception. invalid response')

        try:
            result = Options(**result)
        except ValidationError:
            report_event(f'{self.error_message}: result error', extras={'result': resp.json()})
            raise ThirdPartyError(f'{self.error_message}: request exception. invalid response')

        return result
