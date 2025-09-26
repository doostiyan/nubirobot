import contextlib
import functools
import typing

import requests
from django.conf import settings

from exchange.base.decorators import measure_success_time_cm
from exchange.base.logging import metric_incr
from exchange.base.models import Settings
from exchange.integrations import exceptions
from exchange.integrations.base import VerificationClientBase
from exchange.integrations.types import (
    CardToIbanAPICallResultV2,
    DepositStatusInIbanInquiryEnum,
    IbanInquiry,
    IdentityVerificationClientResult,
    VerificationAPIProviders,
)

if typing.TYPE_CHECKING:
    from exchange.accounts.models import User


class Metrics:
    class MetricType:
        @property
        def value(self):
            return self.__class__.__name__

    class Failure(MetricType):
        def __init__(self, status: str) -> None:
            self.status = status

        @property
        def value(self):
            return self.status

    class Success(MetricType):
        pass

    class SuccessfulCallTime(MetricType):
        pass

    @staticmethod
    def _snake_to_camel(snake: str):
        snake = snake.title().replace('_', '')
        return snake[0].lower() + snake[1:]

    @staticmethod
    def get_metric_name(function: typing.Callable, tp: MetricType):
        metric_key = Metrics._snake_to_camel(function.__name__)
        if isinstance(tp, Metrics.SuccessfulCallTime):
            return f'metric_integrations_JibitIdentity_duration__{metric_key}'

        return f'metric_integrations_JibitIdentity__{metric_key}_{tp.value}'

    @staticmethod
    def meter(func):
        """
        Decorator that measures and logs metrics for the decorated function,
        including handling exceptions and recording success/failure metrics.
        """
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            try:
                with measure_success_time_cm(Metrics.get_metric_name(func, Metrics.SuccessfulCallTime())):
                    return_value = func(*args, **kwargs)
            except Exception as e:
                metric_incr(Metrics.get_metric_name(func, Metrics.Failure(e.__class__.__name__)))
                raise
            metric_incr(Metrics.get_metric_name(func, Metrics.Success()))
            return return_value

        return wrapped

    @staticmethod
    def meter_boolean(func):
        """
        Decorator that measures and logs metrics for the decorated function,
        assuming the function returns a tuple (is_matched, response), and records
        success/failure based on the `is_matched` value and response code.
        """
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            try:
                with measure_success_time_cm(Metrics.get_metric_name(func, Metrics.SuccessfulCallTime())):
                    is_matched, response = func(*args, **kwargs)
            except Exception as e:
                metric_incr(Metrics.get_metric_name(func, Metrics.Failure(e.__class__.__name__)))
                raise
            metrics_type = (
                Metrics.Success()
                if is_matched
                else Metrics.Failure(
                    Metrics._snake_to_camel(response.get('code') or 'Unknown').replace('.', '_'),
                )
            )
            metric_incr(Metrics.get_metric_name(func, metrics_type))
            return is_matched, response
        return wrapped


class JibitVerificationClient(VerificationClientBase):
    name = 'jibit'
    base_url = 'https://napi.jibit.ir/ide'
    access_token_settings_key = 'jibit.ide.access_token'
    refresh_token_settings_key = 'jibit.ide.refresh_token'
    timeout = 5

    @functools.cached_property
    def _access_token(self):
        return Settings.get(self.access_token_settings_key)

    def request(self, url: str, data: dict) -> dict:
        try:
            response = requests.get(
                self.base_url + url,
                headers={
                    'content-type': 'application/json',
                    'authorization': f'Bearer {self._access_token}',
                },
                timeout=self.timeout,
            )
        except requests.RequestException as ex:
            raise exceptions.JibitAPIError('ConnectionError') from ex

        if 400 <= response.status_code <= 499:
            result = response.json()
            err_code: str = result['code']
            if err_code == 'forbidden':
                self.renew_access_token()
                return self.request(url, data)

            for err_code_prefix, exception in (
                ('nationalCode.', exceptions.InvalidNationalCode),
                ('birthDate', exceptions.InvalidBirthDate),
                ('iban.', exceptions.InvalidIBAN),
                ('card.inactive', exceptions.InactiveCard),
                ('card.', exceptions.InvalidCard),
                ('identity_info.not_found', exceptions.NotFound),
                ('mobileNumber.not_valid', exceptions.InvalidMobile),
            ):
                if err_code.startswith(err_code_prefix):
                    raise exception(
                        api_response=result,
                        provider=VerificationAPIProviders.JIBIT.value,
                        msg=result['message'],
                    )

        try:
            response.raise_for_status()
        except requests.HTTPError as ex:
            raise exceptions.JibitAPIError('HTTPError', response.status_code) from ex
        return response.json()

    @Metrics.meter
    def _call_refresh_api(self) -> typing.Tuple[str, str]:
        """returns access and refresh tokens"""
        response = requests.post(self.base_url + '/v1/tokens/refresh', headers={
            'content-type': 'application/json',
        }, json={
            'accessToken': self._access_token,
            'refreshToken': Settings.get(self.refresh_token_settings_key),
        }, timeout=self.timeout)
        response.raise_for_status()
        response = response.json()
        return response['accessToken'], response['refreshToken']

    @Metrics.meter
    def _call_get_token_api(self) -> typing.Tuple[str, str]:
        """returns access and refresh tokens"""
        response = requests.post(self.base_url + '/v1/tokens/generate', headers={
            'content-type': 'application/json',
        }, json={
            'apiKey': settings.JIBIT_IDE_API_KEY,
            'secretKey': settings.JIBIT_IDE_SECRET_KEY,
        }, timeout=self.timeout)
        response.raise_for_status()
        response = response.json()
        return response['accessToken'], response['refreshToken']

    def renew_access_token(self) -> None:
        try:
            access_token, refresh_token = self._call_refresh_api()
        except requests.HTTPError:
            access_token, refresh_token = self._call_get_token_api()

        with contextlib.suppress(AttributeError):
            del self._access_token
        Settings.set(self.access_token_settings_key, access_token)
        Settings.set(self.refresh_token_settings_key, refresh_token)

    @Metrics.meter
    def get_user_identity(self, user: 'User') -> IdentityVerificationClientResult:
        response = self.request(
            '/v1/services/identity/similarity?checkAliveness=true&'
            + '&'.join(
                [
                    f'{k}={v}'
                    for k, v in [
                        ('nationalCode', user.national_code),
                        ('birthDate', user.birthday_shamsi.replace('/', '')),
                        ('fullName', user.get_full_name().replace(' ', '%20')),
                        ('firstName', user.first_name.replace(' ', '%20')),
                        ('lastName', user.last_name.replace(' ', '%20')),
                    ]
                ]
            ),
            {},
        )
        return IdentityVerificationClientResult(
            provider=VerificationAPIProviders.JIBIT,
            api_response=response,
            first_name_similarity=response['firstNameSimilarityPercentage'],
            last_name_similarity=response['lastNameSimilarityPercentage'],
            full_name_similarity=response['fullNameSimilarityPercentage'],
            father_name_similarity=None,
        )

    @Metrics.meter_boolean
    def is_national_code_owner_of_mobile_number(self, national_code: str, mobile: str) -> typing.Tuple[bool, dict]:
        response = self.request(
            f'/v1/services/matching?nationalCode={national_code}&mobileNumber={mobile}',
            {},
        )
        return response['matched'], response

    @Metrics.meter_boolean
    def is_user_owner_of_iban(self, first_name: str, last_name: str, iban: str) -> typing.Tuple[bool, dict]:
        response = self.request(
            f'/v1/services/matching?iban={iban}&name={first_name}%20{last_name}',
            {},
        )
        return response['matched'], response

    @Metrics.meter_boolean
    def is_user_owner_of_bank_card(self, full_name: str, card_number: str) -> typing.Tuple[bool, dict]:
        response = self.request(
            f'/v1/services/matching?cardNumber={card_number}&name={full_name}',
            {},
        )
        return response['matched'], response

    @Metrics.meter
    def convert_card_number_to_iban(self, card_number: str) -> CardToIbanAPICallResultV2:
        response = self.request(
            f'/v1/cards?number={card_number}&iban=true',
            {},
        )

        return CardToIbanAPICallResultV2(
            provider=VerificationAPIProviders.JIBIT,
            api_response=response,
            deposit=response['ibanInfo']['depositNumber'],
            iban=response['ibanInfo']['iban'],
            owners=[owner['firstName'] + ' ' + owner['lastName'] for owner in response['ibanInfo']['owners']],
        )

    @Metrics.meter
    def iban_inquery(self, iban: str) -> IbanInquiry:
        response = self.request(
            f'/v1/ibans?value={iban}',
            {},
        )
        status = response['ibanInfo']['status']
        if status == 'ACTIVE':
            status = DepositStatusInIbanInquiryEnum.ACTIVE.value
        elif status == 'IDLE':
            status = DepositStatusInIbanInquiryEnum.IDLE.value
        elif status == 'BLOCK_WITH_DEPOSIT':
            status = DepositStatusInIbanInquiryEnum.BLOCK_WITH_DEPOSIT.value
        elif status == 'BLOCK_WITHOUT_DEPOSIT':
            status = DepositStatusInIbanInquiryEnum.BLOCK_WITHOUT_DEPOSIT.value
        else:
            status = DepositStatusInIbanInquiryEnum.UNKNOWN.value
        return IbanInquiry(
            provider=VerificationAPIProviders.JIBIT,
            bank=response['ibanInfo']['bank'],
            deposit_number=response['ibanInfo']['depositNumber'],
            iban=response['ibanInfo']['iban'],
            deposit_status=status,
        )
