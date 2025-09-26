import base64
from typing import Optional

from django.conf import settings
from pydantic import ValidationError

from exchange.asset_backed_credit.exceptions import ClientError, ThirdPartyError
from exchange.asset_backed_credit.externals.providers.base import ProviderAPI
from exchange.asset_backed_credit.externals.providers.digipay.provider import DIGIPAY
from exchange.asset_backed_credit.externals.providers.digipay.schema import ResponseSchema, StoresSearchResponseSchema
from exchange.asset_backed_credit.models import UserService
from exchange.asset_backed_credit.types import UserServiceCreateRequest
from exchange.base.logging import report_event, report_exception

_BASE_URL = 'https://api.mydigipay.com/digipay/api' if settings.IS_PROD else 'https://uat.mydigipay.info/digipay/api'


class DigipayAPI(ProviderAPI):
    BASE_URL = _BASE_URL
    provider = DIGIPAY
    error_message: str


class DigipayRenewTokenApi(DigipayAPI):
    url = f'{DigipayAPI.BASE_URL}/oauth/token'
    endpoint_key = 'renewToken'
    method = 'POST'
    need_auth = True
    error_message = 'DigipayRenewToken'
    max_retry = 3
    content_type = 'application/x-www-form-urlencoded'

    def request(self) -> str:
        request_body = {
            'username': self.provider.username,
            'password': self.provider.password,
            'grant_type': 'password',
        }

        try:
            response = self._request(data=request_body)
        except ClientError as e:
            err_msg = f'{self.error_message}: Request Exception'
            report_event(err_msg, extras={'exception': str(e)})
            raise ThirdPartyError(err_msg) from e

        data = response.json()

        access_token = data.get('access_token')
        expires_in = data.get('expires_in')

        if not access_token:
            raise ThirdPartyError(f'{self.error_message}: Invalid Response, missing access_token')

        if not isinstance(expires_in, int):
            raise ThirdPartyError(f'{self.error_message}: Invalid Response, missing expires_in')

        self.provider.set_token(access_token, expires_in)
        return access_token

    def _get_auth_header(self) -> dict:
        client_id, client_secret = self.provider.client_id, self.provider.client_secret
        authorization = base64.b64encode(f'{client_id}:{client_secret}'.encode()).decode()
        return {'Authorization': f'Basic {authorization}'}

    def jsonify_request_data(self, request) -> dict:
        return dict([parts.split('=') for parts in request.body.split('&')])


class DigipayWithAuthAPI(DigipayAPI):
    need_auth = True
    content_type = 'application/json'
    method = 'POST'
    max_retry = 3

    def renew_token(self) -> str:
        return DigipayRenewTokenApi(user_service=self.user_service).request()

    def _get_auth_header(self) -> dict:
        access_token = self.provider.get_token()
        if not access_token:
            access_token = self.renew_token()
        return {'Authorization': 'Bearer ' + access_token}


class DigipayCreateAccountAPI(DigipayWithAuthAPI):
    url = f'{DigipayAPI.BASE_URL}/business/smc/credit-demands/bnpl/activation'
    endpoint_key = 'createAccount'
    error_message = 'DigipayCreateAccount'
    raise_for_status = False

    def __init__(self, user_service: UserService, request_data: UserServiceCreateRequest):
        super().__init__(user_service)
        self.request_data = request_data

    def request(self) -> ResponseSchema:
        request_body = {
            'nationalCode': self.request_data.user_info.national_code,
            'cellNumber': self.request_data.user_info.mobile,
            'birthDate': self._get_birth_date(self.request_data.user_info.birthday_shamsi),
            'amount': self.request_data.amount,
        }

        try:
            response = self._request(json=request_body)
        except ClientError as e:
            err_msg = f'{self.error_message}: Request Exception'
            report_event(err_msg, extras={'exception': str(e)})
            raise ThirdPartyError(err_msg) from e

        try:
            return ResponseSchema(**response.json())
        except ValidationError:
            report_exception()
            raise ThirdPartyError()

    def _get_birth_date(self, birthday_shamsi: str) -> str:
        if not birthday_shamsi:
            return ''

        return birthday_shamsi.replace('/', '-')


class DigipayGetAccountAPI(DigipayWithAuthAPI):
    endpoint_key = 'getAccount'
    error_message = 'DigipayGetAccount'
    method = 'GET'
    raise_for_status = False

    def __init__(self, account_number: str, user_service: Optional[UserService] = None):
        self.url = f'{DigipayAPI.BASE_URL}/business/smc/credit-demands/bnpl/inquiry/{account_number}'
        super().__init__(user_service)

    def request(self) -> ResponseSchema:
        try:
            response = self._request()
        except ClientError as e:
            err_msg = f'{self.error_message}: Request Exception'
            report_event(err_msg, extras={'exception': str(e)})
            raise ThirdPartyError(err_msg) from e

        try:
            return ResponseSchema(**response.json())
        except ValidationError as e:
            report_exception()
            raise ThirdPartyError() from e


class DigipayCloseAccountAPI(DigipayWithAuthAPI):
    endpoint_key = 'closeAccount'
    error_message = 'DigipayCloseAccount'
    method = 'POST'
    raise_for_status = False

    def __init__(self, account_number: str, user_service: Optional[UserService] = None):
        self.url = f'{DigipayAPI.BASE_URL}/business/smc/credit-demands/bnpl/close/{account_number}'
        super().__init__(user_service)

    def request(self) -> ResponseSchema:
        try:
            response = self._request()
        except ClientError as e:
            err_msg = f'{self.error_message}: Request Exception'
            report_event(err_msg, extras={'exception': str(e)})
            raise ThirdPartyError(err_msg) from e

        try:
            return ResponseSchema(**response.json())
        except ValidationError:
            report_exception()
            raise ThirdPartyError()


class DigipayStoresAPI(DigipayWithAuthAPI):
    endpoint_key = 'getStores'
    error_message = 'DigipayGetStores'
    method = 'POST'
    raise_for_status = False

    def __init__(self, page: int = 0, size: int = 250):
        self.url = f'{DigipayAPI.BASE_URL}/dpx/stores/search?page={page}&size={size}'
        super().__init__()

    def request(self) -> StoresSearchResponseSchema:
        try:
            response = self._request(
                json={
                    'restrictions': [
                        {'type': 'simple', 'field': 'state.disabled', 'operation': 'eq', 'value': False},
                        {'type': 'collection', 'field': 'types', 'operation': 'eq', 'values': [0]},
                    ],
                    'orders': [{'order': 'asc', 'field': 'priority'}],
                }
            )
        except ClientError as e:
            err_msg = f'{self.error_message}: Request Exception'
            report_event(err_msg, extras={'exception': str(e)})
            raise ThirdPartyError(err_msg) from e

        try:
            return StoresSearchResponseSchema(**response.json())
        except ValidationError:
            report_exception()
            raise ThirdPartyError(self.error_message)
