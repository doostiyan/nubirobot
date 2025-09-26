from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import parse_qs, urlparse

import requests
from django.conf import settings
from django.core.cache import cache
from jsonschema.exceptions import ValidationError
from jsonschema.validators import validate as jsonschema_validate

from exchange.asset_backed_credit.exceptions import ClientError, ThirdPartyError
from exchange.asset_backed_credit.externals.providers.base import ProviderAPI
from exchange.asset_backed_credit.models import Service, UserService
from exchange.asset_backed_credit.schema.vency import CALCULATOR_JSON_SCHEMA
from exchange.asset_backed_credit.services.providers.provider import SignSupportProvider
from exchange.asset_backed_credit.types import ProviderBasedLoanCalculationData, ProviderFeeType, UserServiceCreateRequest
from exchange.base.decorators import measure_time_cm
from exchange.base.logging import report_event

VENCY_BASE_URL = 'https://api.vency.ir' if settings.IS_PROD else 'https://api.vencytest.ir'
VENCY_REDIRECT_URL = (
    'https://gateway.vency.ir/main/select/{order_id}'
    if settings.IS_PROD
    else 'https://gateway.vencytest.ir/main/select/{order_id}'
)


@dataclass
class VencyProvider(SignSupportProvider):
    """
    This class inherits SignSupportProvider class.

    Attributes:
        pub_key (str): The public key used for signature verification.

    Use this to login into vency account in nobitex:
        testnet_nobitex_username = '09999999967'
        testnet_nobitex_password = 'Z>h)F~k?zTN!;j4'
    """

    contract_id: str
    username: str
    password: str
    client_id: str
    client_secret: str


VENCY = VencyProvider(
    name='vency',
    ips=(['185.53.140.24'] if settings.IS_PROD else ['81.12.30.43', '80.210.37.142', '37.32.127.132']),
    pub_key=(
        '''-----BEGIN PUBLIC KEY-----
        MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAw49g+pzjEiP8XUqvEdAO
        m5a0pRduZXjS9i2B6fL4QYbSAQ9t1gq7dSlfKz8lAaTthiH2cMJCGNMxMeFvzJP/
        rK4xgOwlbDTnLwjmKPknlvB49ntuukzpySQZsZ9/sa9gHAMUscNP/8wMTsQDqBsr
        I5mlf93qkTfmodLuRJVYMlxmW5xG1nTCnA017Q//vbuF4sA2J7nQT8aHoTg8Gtra
        VhfR+fK+p3s2qaHYC8jHoqiA723uwPhid5120F0g7rTPP8AGDLJdCf4dqHxG8RZN
        +0fQm31Pl48sbceXyAo/mDU6IpustbPZ8k0XscENCGGhQLiNK6OkkW+U95xeTT0t
        pwIDAQAB
        -----END PUBLIC KEY-----'''
    )
    if settings.IS_PROD
    else '',
    id=Service.PROVIDERS.vency,
    contract_id=('' if settings.IS_PROD else ''),
    account_id=(8119834 if settings.IS_PROD else 319514 if settings.IS_TESTNET else 912),
    username='' if settings.IS_PROD else '',
    password='' if settings.IS_PROD else '',
    client_id=settings.ABC_VENCY_CLIENT_ID if settings.IS_PROD or settings.IS_TESTNET else 'test-client-id',
    client_secret=settings.ABC_VENCY_CLIENT_SECRET if settings.IS_PROD or settings.IS_TESTNET else 'test-client-secret',
)


class VencyAPI(ProviderAPI):
    provider = VENCY
    error_message = None
    content_type = None


class VencyRenewTokenAPI(VencyAPI):
    url = f'{VENCY_BASE_URL}/oauth2/token'
    endpoint_key = 'renewToken'
    method = 'POST'
    need_auth = False
    error_message = 'VencyRenewToken'
    max_retry = 3
    content_type = 'application/x-www-form-urlencoded'

    SCOPES = ' '.join(
        (
            'collaborator:lending:orders:calculation',
            'collaborator:lending:orders:create',
            'collaborator:orders:cancel',
            'collaborator:orders:readAll',
        )
    )

    def request(self):
        try:
            resp = self._request(data=self._get_request_data())
        except (ValueError, ClientError) as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        data = resp.json()
        access_token = data.get('access_token')
        if not access_token:
            raise ThirdPartyError(f'{self.error_message}: invalid response, missing access_token')

        expires_in = data.get('expires_in')
        if not isinstance(expires_in, int):
            raise ThirdPartyError(f'{self.error_message}: invalid response, expect int expires_in')

        self.provider.set_token(access_token, expires_in)
        return access_token

    @classmethod
    def _get_request_data(cls):
        return {
            'grant_type': 'client_credentials',
            'client_id': VENCY.client_id,
            'client_secret': VENCY.client_secret,
            'scope': cls.SCOPES,
        }

    def jsonify_request_data(self, request):
        return dict([parts.split('=') for parts in request.body.split('&')])


class VencyWithAuthAPI(VencyAPI):
    need_auth = True

    def _get_auth_header(self) -> Dict:
        token = self.provider.get_token()
        if not token:
            token = self.renew_token()
        return {'Authorization': 'Bearer ' + token}

    def renew_token(self):
        return VencyRenewTokenAPI(self.user_service).request()


class VencyCreateAccountAPI(VencyWithAuthAPI):
    url = f'{VENCY_BASE_URL}/v3/lending/collaborators/orders'
    method = 'POST'
    content_type = 'application/json'
    endpoint_key = 'createAccount'
    error_message = 'VencyCreateAccount'

    def __init__(self, user_service: UserService, request_data: UserServiceCreateRequest):
        super().__init__(user_service)
        self.request_data = request_data

    @measure_time_cm(metric='vency_create_account')
    def request(self):
        try:
            resp = self._request(json=self._get_request_body())
        except (ValueError, ClientError) as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        try:
            data = self._get_response_data(resp)
        except ThirdPartyError as e:
            report_event(f'{self.error_message}: result error', extras={'result': resp.json()})
            raise e

        return data

    def _get_request_body(self):
        return {
            'uniqueIdentifier': self.request_data.unique_id,
            'amountRials': self.request_data.amount,
            'loanPrincipalSupplyPlanId': self.request_data.extra_info['loanPrincipalSupplyPlanId'],
            'collaboratorLoanPlanId': self.request_data.extra_info['collaboratorLoanPlanId'],
            'customerNationalCode': self.request_data.user_info.national_code,
        }

    def _get_response_data(self, response: requests.Response):
        """
        expected response format: {
            'orderId': str,
            'uniqueIdentifier': str,
            'redirectUrl: str
        }
        """

        data = response.json()
        if not data.get('orderId'):
            raise ThirdPartyError(f'{self.error_message}: invalid response, missing orderId')
        if not data.get('uniqueIdentifier') == self.request_data.unique_id:
            raise ThirdPartyError(f'{self.error_message}: invalid response, expected unique identifier')
        if not data.get('redirectUrl'):
            raise ThirdPartyError(f'{self.error_message}: invalid response, missing redirectUrl')
        return data


class VencyGetOrderAPI(VencyWithAuthAPI):
    url = '{base_url}/v3/collaborators/orders/{account_number}'
    method = 'GET'
    endpoint_key = 'getOrder'
    error_message = 'VencyGetOrder'

    def __init__(self, user_service: Optional[UserService] = None) -> None:
        self.url = self.get_url(account_number=user_service.account_number)
        super().__init__(user_service=user_service)

    @measure_time_cm(metric='vency_get_order')
    def request(self):
        try:
            resp = self._request()
        except (ValueError, ClientError) as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        data = resp.json()
        if not data.get('status'):
            raise ThirdPartyError(f'{self.error_message}: invalid response, missing status')

        order_id = data.get('orderId')
        if not order_id:
            raise ThirdPartyError(f'{self.error_message}: invalid response, missing orderId')

        if not data.get('redirectUrl'):
            data['redirectUrl'] = VENCY_REDIRECT_URL.format(order_id=order_id)

        unique_id = data.get('uniqueIdentifier')
        if not unique_id or unique_id != self.user_service.account_number:
            raise ThirdPartyError(f'{self.error_message}: invalid response, expected unique identifier')

        return data

    @classmethod
    def get_url(cls, account_number):
        return cls.url.format(base_url=VENCY_BASE_URL, account_number=account_number)

    def validate_response(self, response: requests.Response):
        return response


class VencyCancelOrderAPI(VencyWithAuthAPI):
    url = '{base_url}/v3/collaborators/orders/{account_number}/cancel'
    method = 'PUT'
    content_type = 'application/json'
    endpoint_key = 'cancelOrder'
    error_message = 'VencyCancelOrder'

    def __init__(self, user_service: Optional[UserService] = None) -> None:
        self.url = self.get_url(account_number=user_service.account_number)
        super().__init__(user_service=user_service)

    @measure_time_cm(metric='vency_cancel_order')
    def request(self):
        self.url = self.get_url(account_number=self.user_service.account_number)
        try:
            resp = self._request()
        except (ValueError, ClientError) as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        return resp.ok

    @classmethod
    def get_url(cls, account_number):
        return cls.url.format(base_url=VENCY_BASE_URL, account_number=account_number)

    def validate_response(self, response: requests.Response):
        return response


class VencyCalculatorAPI(VencyWithAuthAPI):
    url = f'{VENCY_BASE_URL}/v3/lending/collaborators/orders/calculation'
    method = 'GET'
    endpoint_key = 'calculator'
    error_message = 'VencyCalculator'
    content_type = None

    response_schema = CALCULATOR_JSON_SCHEMA

    CACHE_KEY_FORMAT = 'abc:provider:vency:calculator:{principal}'
    CACHE_TIMEOUT = 5 * 60

    def __init__(self, principal: int, period: int):
        super().__init__()
        self.principal = principal
        self.period = period

    @measure_time_cm(metric='vency_calculator')
    def request(self):
        response_data = self._get_cached_response(principal=self.principal)
        if not response_data:
            try:
                resp = self._request(params={'amountRials': int(self.principal)})
            except (ValueError, ClientError) as e:
                report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
                raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

            response_data = resp.json()
            try:
                jsonschema_validate(response_data, self.response_schema)
            except ValidationError as e:
                report_event(f'{self.error_message}: result error', extras={'result': str(e)})
                raise ThirdPartyError(f'{self.error_message}: invalid response schema') from e

            self._cache_response(principal=self.principal, result=response_data)

        return self._get_calculator_data(data=response_data)

    def _get_calculator_data(self, data):
        data = data[0]
        term = [item for item in data['durations'] if item['termMonth'] == self.period]
        if not term:
            raise ThirdPartyError(f'{self.error_message}: no loan term found')

        term = term[0]
        installments = [installment for installment in term['installments'] if installment['type'] == 'INSTALLMENT']
        if not installments:
            raise ThirdPartyError(f'{self.error_message}:no installment found')

        try:
            installment_amount = term['installmentRials']
            total_installments_amount = term['paymentRials']
            provider_fee_amount = term['operationFee']['totalFeeRials']
        except KeyError:
            raise ThirdPartyError(f'{self.error_message}: invalid calculation data')

        return ProviderBasedLoanCalculationData(
            principal=self.principal,
            period=self.period,
            interest_rate=data['interestRateAPR'],
            provider_fee_percent=term['operationFee']['totalFeePercent'],
            provider_fee_amount=provider_fee_amount,
            provider_fee_type=ProviderFeeType.PRE_PAID,
            installment_amount=installment_amount,
            total_installments_amount=total_installments_amount,
            extra_info={
                'loanPrincipalSupplyPlanId': term['loanPrincipalSupplyPlanId'],
                'collaboratorLoanPlanId': term['collaboratorLoanPlanId'],
            },
        )

    def _get_cached_response(self, principal):
        key = self.CACHE_KEY_FORMAT.format(principal=principal)
        return cache.get(key)

    def _cache_response(self, principal, result):
        key = self.CACHE_KEY_FORMAT.format(principal=principal)
        cache.set(key, result, timeout=self.CACHE_TIMEOUT)

    @staticmethod
    def jsonify_request_data(request):
        return parse_qs(urlparse(request.url).query)
