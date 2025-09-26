from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Dict, Optional

from django.conf import settings
from django.utils.timezone import now

from exchange.asset_backed_credit.exceptions import ClientError, ThirdPartyError
from exchange.asset_backed_credit.externals.providers.base import ProviderAPI
from exchange.asset_backed_credit.models import Service, UserService
from exchange.asset_backed_credit.services.providers.provider import SignSupportProvider
from exchange.asset_backed_credit.types import UserServiceCreateRequest
from exchange.base.decorators import measure_time_cm
from exchange.base.logging import report_event

TARA_BASE_URL = 'https://club.tara-club.ir/' if settings.IS_PROD else 'https://stage.tara-club.ir/'


@dataclass
class TaraProvider(SignSupportProvider):
    """
    This class inherits Provider class.

    Attributes:
        pub_key (str): The public key used for signature verification.

    Use this to login into tara account in nobitex:
        testnet_nobitex_username = '09999999968'
        testnet_nobitex_password = 'J54GjCXdYrrZ#s%#gzGnaZSWUcYWcT'
    """

    contract_id: str
    channel_id: str
    username: str
    password: str


TARA = TaraProvider(
    name='tara',
    ips=(
        []
        if settings.IS_PROD
        else [
            '5.202.253.78',  # TARA IP
            '194.156.140.191',  # TARA IP
            '194.156.140.192',  # TARA IP
        ]
    ),
    pub_key=(
        '''-----BEGIN PUBLIC KEY-----
        MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxVNT/n6jbG3MImD+WOVe
        +Knbgku+DIEuDgr91EMXtoTHDw6FGn8v8Focm3f494IINhKTKLzecZlN1GQ4tu0Z
        kNCPd3KWV0wkkRt/rLQU9MuFy64Gv2CbEYgXRE8DUT68xn3q/PsEQH/meWT602z8
        +l7cbwOzcGUhRvTqMaXFrcE5zMUT/dSbI8rwHSThWOITBPqjJmQ1grEyK9MoZ6gP
        MaLNNnzo7i457ppXWaiR40mpC8sGMdjDMn+hVYRBu65YUNr51wZVwbpgsR/QK3M+
        kZ2NeS1gxSPRaeKzDWsksXr5GZqr2cQYjjRAJtpE0a88NmE0rqMzOr/lsIZFqbh3
        yQIDAQAB
        -----END PUBLIC KEY-----'''
    )
    if settings.IS_PROD
    else (
        '''-----BEGIN PUBLIC KEY-----
        MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA9A36mMMX0T3esUOSCMzo
        FLdRUYvGyzq6/qqaonvT3kvF1kS6K37+CWmmf9oOiLBHBH6CwgJFFgXtK/0Mu4zF
        omLHDk/zldgSmxZlQDuElUK7w89NZExB/atMV2svf+TxjQLGf6kSV8vPhUuLdD44
        KAcu+Ypgzpug1rE1ccfPtIIVBbzZoUByi/zqp8X8BDiEvg1a+ayrDPhArd210sJ8
        xz25yN8WspEYJtc8ZB9Lxnws4tKjC+TAAc1Xi62lE3nQMA339AiWjp12E0Wezi69
        U8JnsUvI3Lj1b2OePO9sD5oWWIuR6mkL2QS1jaeP2KY7pYAOgE9BMvhp9srge7Fu
        lwIDAQAB
        -----END PUBLIC KEY-----'''
    ),
    id=Service.PROVIDERS.tara,
    contract_id=('961' if settings.IS_PROD else '774'),
    channel_id=('2834569' if settings.IS_PROD else '42099'),
    account_id=(6795485 if settings.IS_PROD else 318073 if settings.IS_TESTNET else 910),
    username=settings.ABC_CREDIT_TARA_USERNAME if settings.IS_PROD else 'nobitex_credit',
    password=settings.ABC_CREDIT_TARA_PASSWORD if settings.IS_PROD else '1qaz@WSX',
)


class TaraAPI(ProviderAPI):
    provider = TARA
    error_message: str
    content_type = 'application/json'

    def _get_auth_header(self) -> Dict:
        token = self.provider.get_token()
        if not token:
            token = self.renew_token()
        return {'Authorization': 'Bearer ' + token}


class TaraRenewToken(TaraAPI):
    url = TARA_BASE_URL + 'club/api/v1/user/login/credit/'
    endpoint_key = 'renewToken'
    method = 'post'
    need_auth = False
    error_message = 'TaraRenewToken'
    max_retry = 3

    @measure_time_cm(metric='tara_renewToken')
    def request(self):
        data = {'principal': self.provider.username, 'password': self.provider.password}
        try:
            api_result = self._request(json=data)
        except (ValueError, ClientError) as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        result = api_result.json()
        if (
            not result.get('success')
            or not result.get('accessCode')
            or not isinstance(result.get('expiryDuration'), int)
        ):
            report_event(f'{self.error_message}: result error', extras={'result': result})
            raise ThirdPartyError(f'{self.error_message}: Fail to renew token')
        access_token = result['accessCode']
        self.provider.set_token(access_token, int(result['expiryDuration']))
        return access_token


class TaraAPIWithAuth(TaraAPI):
    method = 'post'
    need_auth = True

    def __init__(self, user_service: UserService) -> None:
        super().__init__(user_service)
        self.user = user_service.user

    def renew_token(self) -> Optional[str]:
        return TaraRenewToken(self.user_service).request()


class TaraCreateAccount(TaraAPIWithAuth):
    url = f'{TARA_BASE_URL}club/api/v1/limited/account/create/{TARA.contract_id}'
    endpoint_key = 'createAccount'
    error_message = 'TaraCreateAccount'

    def __init__(self, user_service: UserService, request_data: UserServiceCreateRequest):
        super().__init__(user_service)
        self.request_data = request_data

    @measure_time_cm(metric='tara_createAccount')
    def request(self):
        data = {
            'mobile': self.request_data.user_info.mobile,
            'nationalCode': self.request_data.user_info.national_code,
            'name': self.request_data.user_info.first_name,
            'family': self.request_data.user_info.last_name,
            'sign': self.sign(
                f'{self.provider.contract_id},{self.request_data.user_info.mobile},{self.request_data.user_info.national_code}'
            ),
        }
        try:
            api_result = self._request(json=data)
        except (ClientError, ValueError) as e:
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        result = api_result.json()
        if not result.get('success') or not result.get('accountNumber'):
            report_event(f'{self.error_message}: result error', extras={'result': result})
            raise ThirdPartyError(f'{self.error_message}: Fail to create account')
        return result.get('accountNumber')


class TaraGetTraceNumber(TaraAPIWithAuth):
    url = None
    endpoint_key = 'getTraceNumber'
    error_message = 'TaraGetTraceNumber'
    timeout = 10

    def __init__(self, tp: str, user_service: UserService) -> None:
        self.url = f'{TARA_BASE_URL}club/api/v1/limited/account/transaction/trace/{TARA.contract_id}/{tp}'
        super().__init__(user_service)

    @measure_time_cm(metric='tara_getTraceNumber')
    def request(self, amount: Decimal):
        data = {
            'mobile': self.user.mobile,
            'nationalCode': self.user.national_code,
            'amount': str(int(amount)),
        }
        try:
            api_result = self._request(json=data)
        except (ClientError, ValueError) as e:
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        result = api_result.json()
        if not result.get('success') or not result.get('traceNumber'):
            report_event(f'{self.error_message}: result error', extras={'result': result})
            raise ThirdPartyError(f'{self.error_message}: Fail to get a trace number')
        return result.get('traceNumber')


class TaraChargeToAccount(TaraAPIWithAuth):
    url = f'{TARA_BASE_URL}club/api/v2/limited/account/transaction/charge/to/{TARA.contract_id}'
    endpoint_key = 'chargeAccount'
    error_message = 'TaraChargeAccount'

    def __init__(self, user_service: UserService, amount: Decimal) -> None:
        super().__init__(user_service)
        self.amount = str(int(amount))

    @measure_time_cm(metric='tara_chargeAccount')
    def request(self):
        trace_number = self.get_trace_number(self.amount)
        data = {
            'mobile': self.user.mobile,
            'nationalCode': self.user.national_code,
            'amount': self.amount,
            'sign': self.sign(
                f'{self.provider.contract_id},{self.user.mobile},{self.user.national_code},{self.amount}',
            ),
            'traceNumber': trace_number,
        }
        try:
            api_result = self._request(json=data)
        except (ClientError, ValueError) as e:
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        result = api_result.json()
        if not result.get('success') or not result.get('referenceNumber'):
            report_event(f'{self.error_message}: result error', extras={'result': result})
            trace_number, status, amount = TaraAccountTransactionInquiry(
                user_service=self.user_service, trace_number=trace_number
            ).request()
            if not status or int(self.amount) != amount:
                raise ThirdPartyError(f'{self.error_message}: Fail to charge account')
            else:
                return trace_number
        return result.get('referenceNumber')

    def get_trace_number(self, amount) -> Optional[str]:
        return TaraGetTraceNumber(tp='charge', user_service=self.user_service).request(amount=amount)


class TaraDischargeAccount(TaraAPIWithAuth):
    url = f'{TARA_BASE_URL}club/api/v1/limited/account/transaction/discharge/{TARA.contract_id}'
    endpoint_key = 'dischargeAccount'
    error_message = 'TaraDischargeAccount'

    def __init__(self, user_service: UserService, amount: Decimal) -> None:
        super().__init__(user_service)
        self.amount = str(int(amount))

    @measure_time_cm(metric='tara_dischargeAccount')
    def request(self):
        trace_number = self.get_trace_number(self.amount)
        data = {
            'mobile': self.user.mobile,
            'nationalCode': self.user.national_code,
            'amount': self.amount,
            'sign': self.sign(
                f'{self.provider.contract_id},{self.user.mobile},{self.user.national_code},{self.amount}',
            ),
            'traceNumber': trace_number,
        }

        try:
            api_result = self._request(json=data)
        except (ClientError, ValueError) as e:
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        result = api_result.json()
        if not result.get('success') or not result.get('referenceNumber'):
            report_event(f'{self.error_message}: result error', extras={'result': result})
            raise ThirdPartyError(f'{self.error_message}: Fail to discharge account')
        return result.get('referenceNumber')

    def get_trace_number(self, amount) -> Optional[str]:
        return TaraGetTraceNumber(tp='decharge', user_service=self.user_service).request(amount=amount)


class TaraCheckUserBalance(TaraAPIWithAuth):
    url = f'{TARA_BASE_URL}club/api/v2/limited/account/balance/{TARA.contract_id}'
    endpoint_key = 'checkUserBalance'
    error_message = 'TaraCheckUserBalance'
    timeout = 5

    @measure_time_cm(metric='tara_checkUserBalance')
    def request(self):
        data = {
            'mobile': self.user.mobile,
            'nationalCode': self.user.national_code,
            'accountNumber': self.user_service.account_number,
            'sign': self.sign(
                f'{self.provider.contract_id},{self.user.mobile},{self.user.national_code},{self.user_service.account_number}',
            ),
        }
        try:
            api_result = self._request(json=data)
        except (ClientError, ValueError) as e:
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        result = api_result.json()
        if not result.get('success') or not result.get('balance'):
            report_event(f'{self.error_message}: result error', extras={'result': result})
            raise ThirdPartyError(f'{self.error_message}: Fail to get balance')
        return Decimal(result.get('balance'))


class TaraTotalInstallments(TaraAPIWithAuth):
    url = ''
    endpoint_key = 'totalInstallments'
    error_message = 'TaraTotalInstallments'
    timeout = 5

    def __init__(self, user_service: UserService) -> None:
        date = (now() + timedelta(days=90)).strftime('%Y-%m-%d')
        self.url = (
            f'{TARA_BASE_URL}credit/api/external/credit/loan/v1/installment/user/total/'
            f'{date}/{TARA.channel_id}/{TARA.contract_id}/0/1'
        )
        super().__init__(user_service)

    @measure_time_cm(metric='tara_totalInstallments')
    def request(self):
        national_code = self.user.national_code
        mobile = self.user.mobile
        data = {
            'mobile': mobile,
            'nationalCode': national_code,
            'status': 'NOT_SETTLED',
            'sign': self.sign(f'{national_code},{mobile}'),
        }
        try:
            api_result = self._request(json=data)
        except (ClientError, ValueError) as e:
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        result = api_result.json()
        if not result.get('value') or not result['value'].get('items'):
            report_event(f'{self.error_message}: result error', extras={'result': result})
            raise ThirdPartyError(f'{self.error_message}: Fail to get total installments')

        not_settled_items = [item for item in result['value']['items'] if item.get('status') == 'NOT_SETTLED']
        if not not_settled_items:
            report_event(f'{self.error_message}: amount does not exist', extras={'result': result})
            raise ThirdPartyError(f'{self.error_message}: Fail to get total installments')

        not_settled_amount = 0
        for item in not_settled_items:
            if not self._is_item_valid(item):
                report_event(f'{self.error_message}: result error', extras={'result': result})
                raise ThirdPartyError(f'{self.error_message}: Fail to get total installments')

            not_settled_amount += item['amount']
        return not_settled_amount

    def _is_item_valid(self, item):
        return all(
            [
                'nationalCode' in item,
                item['nationalCode'] == self.user.national_code,
                'mobile' in item,
                item['mobile'] == self.user.mobile,
                'amount' in item,
                item['amount'] is not None,
            ]
        )


class TaraAccountTransactionInquiry(TaraAPIWithAuth):
    url = None
    endpoint_key = 'accountTransactionInquiry'
    error_message = 'TaraAccountTransactionInquiry'
    timeout = 10
    max_retry = 3

    def __init__(self, trace_number: str, user_service: UserService) -> None:
        self.url = f'{TARA_BASE_URL}club/api/v2/limited/account/transaction/{TARA.contract_id}/inquiry/{trace_number}'
        super().__init__(user_service)

    @measure_time_cm(metric='tara_accountTransactionInquiry')
    def request(self):
        try:
            api_result = self._request(json={})
        except (ClientError, ValueError) as e:
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        result = api_result.json()
        if result.get('id') is None or result.get('status') is None or result.get('doTime') is None:
            report_event(f'{self.error_message}: result error', extras={'result': result})
            raise ThirdPartyError(f'{self.error_message}: Fail to get account transaction inquiry')
        return result.get('id'), result.get('status'), result.get('amount')
