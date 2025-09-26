import base64
import time
from typing import Dict, List

from django.conf import settings
from pydantic import TypeAdapter, ValidationError

from exchange.asset_backed_credit.exceptions import ClientError, ThirdPartyError
from exchange.asset_backed_credit.externals.providers.base import ProviderAPI
from exchange.asset_backed_credit.externals.providers.parsian.provider import PARSIAN
from exchange.asset_backed_credit.externals.providers.parsian.schema import (
    CitySchema,
    GetRequestResponseSchema,
    IssueChildCardResponseSchema,
    IssueChildCardSchema,
    ProvinceSchema,
)
from exchange.asset_backed_credit.models import CardRequestSchema
from exchange.asset_backed_credit.services.debit.schema import DebitCardUserInfoSchema
from exchange.base.decorators import cached_method, measure_time_cm
from exchange.base.logging import report_event


class ParsianAPI(ProviderAPI):
    BASE_URL = 'https://issuer.pec.ir'
    provider = PARSIAN
    content_type = 'application/json'
    need_auth = True

    PARENT_CARD_NUMBER = settings.ABC_DEBIT_PARSIAN_PARENT_CARD_NUMBER
    PARENT_CARD_PASSWORD = settings.ABC_DEBIT_PARSIAN_PARENT_CARD_PASSWORD

    def _get_auth_header(self) -> Dict:
        username, password = self.provider.username, self.provider.password
        authorization = base64.b64encode(f'{username}:{password}'.encode()).decode()
        return {'Authorization': f'Basic {authorization}'}


class ParsianGetRequest(ParsianAPI):
    url = f'{ParsianAPI.BASE_URL}/pec/api/issuer/getRequest'
    endpoint = 'issuerGetRequest'
    method = 'POST'
    error_message = 'ParsianIssuerGetRequest'
    endpoint_key = 'IssuerGetRequest'

    def __init__(self, request_id: str) -> None:
        super().__init__()
        self.request_id = request_id

    @measure_time_cm(metric='abc_parsian_issuerGetRequest')
    def request(self):
        data = {'RequestId': self.request_id, 'ParentCardNumber': self.PARENT_CARD_NUMBER}
        try:
            resp = self._request(json=data)
        except ClientError as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        try:
            result = GetRequestResponseSchema(**resp.json())
        except ValidationError as e:
            report_event(f'{self.error_message}: result error', extras={'result': resp.json()})
            raise ThirdPartyError(f'{self.error_message}: invalid response') from e

        if not result.is_success or result.error_code:
            report_event(f'{self.error_message}: result error', extras={'result': result})
            raise ThirdPartyError(f'{self.error_message}: Fail to create account')
        return result


class IssueChildCardAPI(ParsianAPI):
    url = f'{ParsianAPI.BASE_URL}/pec/api/issuer/issueChildCard'
    method = 'POST'
    endpoint_key = 'issueChildCard'
    error_message = 'ParsianIssueChildCard'

    _DESIGN_CODE_MAPPING = {
        CardRequestSchema.ColorChoices.CARBON: '14535-Meshki',
        CardRequestSchema.ColorChoices.GOLD: '14535-Piazi',
        CardRequestSchema.ColorChoices.ROSE_GOLD: '14535-Mesi',
        CardRequestSchema.ColorChoices.OLIVE: '14535-Khaki',
        CardRequestSchema.ColorChoices.AMBER: '14535-Golbehi',
        CardRequestSchema.ColorChoices.VIOLET: '14535-Banafsh',
    }

    @measure_time_cm(metric='abc_parsian_issue_child_card')
    def request(self, user_info: DebitCardUserInfoSchema) -> IssueChildCardResponseSchema:
        try:
            resp = self._request(json=self._get_request_data(user_info))
        except (ClientError, ThirdPartyError) as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        try:
            return IssueChildCardResponseSchema(**resp.json())
        except ValidationError as e:
            report_event(f'{self.error_message}: result error', extras={'result': resp.json()})
            raise ThirdPartyError(f'{self.error_message}: invalid response') from e

    def _get_request_data(self, user_info: DebitCardUserInfoSchema) -> Dict:
        province_id = GetProvinceAPI().request(name=user_info.province)
        city_id = GetCityAPI().request(province_id=province_id, name=user_info.city)
        child_card_info = IssueChildCardSchema(
            birth_cert_no=user_info.birth_cert_no,
            national_code=user_info.national_code,
            first_name=user_info.first_name,
            last_name=user_info.last_name,
            first_name_en=user_info.first_name_en,
            last_name_en=user_info.last_name_en,
            gender=user_info.gender,
            father_name=user_info.father_name,
            birth_date=user_info.birth_date,
            cell_number=user_info.mobile,
            address=user_info.address,
            zip_code=user_info.postal_code,
        )

        return {
            'FeeAmount': 0,
            'CityId': city_id,
            'SecondPassword': ParsianAPI.PARENT_CARD_PASSWORD,
            'ParentCardNumber': ParsianAPI.PARENT_CARD_NUMBER,
            'Indicator': self._get_random_indicator(user_info.national_code, user_info.mobile),
            'DesignCode': self._get_design_code(color=user_info.color),
            'Detail': [child_card_info.model_dump(by_alias=True)],
        }

    @staticmethod
    def _get_random_indicator(national_code, mobile_number):
        w1 = ''.join(str((int(c) + 7) % 7) for c in national_code)
        w2 = ''.join(str((int(c) + 5) % 10) for c in mobile_number)
        indicator = w2[2:4] + w1[1:3] + w2[9:] + w1[6:8] + w2[6:8]
        return indicator

    @classmethod
    def _get_design_code(cls, color: int):
        return cls._DESIGN_CODE_MAPPING[color]


class GetProvinceAPI(ParsianAPI):
    url = f'{ParsianAPI.BASE_URL}/pec/api/issuer/getProvince'
    method = 'POST'
    endpoint_key = 'getProvince'
    error_message = 'ParsianGetProvince'

    CACHE_TIMEOUT = 1 * 24 * 60 * 60

    @measure_time_cm(metric='abc_parsian_get_province')
    def request(self, name: str) -> int:
        provinces_data = self._get_provinces_data()
        provinces = TypeAdapter(List[ProvinceSchema]).validate_python(provinces_data)

        province_id = None
        for province in provinces:
            if ''.join(province.title.split()) == ''.join(name.split()):
                province_id = province.id
                break

        if province_id is None:
            report_event(f'{self.error_message}: invalid response', extras={'data': provinces_data, 'name': name})
            raise ThirdPartyError(f'{self.error_message}: invalid response')

        return province_id

    @cached_method(timeout=CACHE_TIMEOUT)
    def _get_provinces_data(self) -> list:
        try:
            resp = self._request()
        except (ClientError, ThirdPartyError) as e:
            report_event(f'{self.error_message}: third-party error', extras={'data': str(e)})
            raise ThirdPartyError(f'{self.error_message}: third-party error') from e

        result = resp.json()
        provinces_data = result.get('GetProvinceDetails')

        if provinces_data is None:
            report_event(f'{self.error_message}: invalid response', extras={'data': result})
            raise ThirdPartyError(f'{self.error_message}: invalid response')

        try:
            TypeAdapter(List[ProvinceSchema]).validate_python(provinces_data)
        except ValidationError as e:
            report_event(f'{self.error_message}: invalid response', extras={'data': provinces_data})
            raise ThirdPartyError(f'{self.error_message}: invalid response') from e

        return provinces_data


class GetCityAPI(ParsianAPI):
    url = f'{ParsianAPI.BASE_URL}/pec/api/issuer/getCities'
    method = 'POST'
    endpoint_key = 'getCity'
    error_message = 'ParsianGetCities'

    CACHE_TIMEOUT = 1 * 24 * 60 * 60

    @measure_time_cm(metric='abc_parsian_get_cities')
    def request(self, province_id: int, name: str) -> int:
        cities_data = self._get_cities_data(province_id=province_id)
        cities = TypeAdapter(List[CitySchema]).validate_python(cities_data)

        city_id = None
        for city in cities:
            if ''.join(city.title.split()) == ''.join(name.split()):
                city_id = city.id
                break

        if city_id is None:
            report_event(f'{self.error_message}: invalid response', extras={'result': cities_data, 'name': name})
            raise ThirdPartyError(f'{self.error_message}: invalid response')

        return city_id

    @cached_method(timeout=CACHE_TIMEOUT)
    def _get_cities_data(self, province_id: int) -> list:
        try:
            resp = self._request(json={'ProvinceId': province_id})
        except (ClientError, ThirdPartyError) as e:
            report_event(f'{self.error_message}: third-party error', extras={'data': str(e)})
            raise ThirdPartyError(f'{self.error_message}: third-party error') from e

        result = resp.json()
        cities_data = result.get('Data')

        if cities_data is None:
            report_event(f'{self.error_message}: invalid response', extras={'data': result, 'province_id': province_id})
            raise ThirdPartyError(f'{self.error_message}: invalid response')

        try:
            TypeAdapter(List[CitySchema]).validate_python(cities_data)
        except ValidationError as e:
            report_event(
                f'{self.error_message}: invalid response', extras={'data': cities_data, 'province_id': province_id}
            )
            raise ThirdPartyError(f'{self.error_message}: invalid response') from e

        return cities_data


class DebitCardOTPRequestAPI(ParsianAPI):
    url = f'{ParsianAPI.BASE_URL}/pec/api/Issuer/SendSMSToCardHolder'
    method = 'POST'
    endpoint_key = 'otpRequest'
    error_message = 'ParsianOtpRequest'

    @measure_time_cm(metric='abc_parsian_debit_card_otp_request')
    def request(self, pan: str):
        last_4_digits = pan[-4:]
        try:
            hashed_pan = DebitCardHashPanAPI().request(pan=pan)
            resp = self._request(json={'CardNumberHash': hashed_pan, 'LastFourDigitNumber': last_4_digits})
        except ThirdPartyError as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        return resp.json().get('IsSuccess')


class DebitCardHashPanAPI(ParsianAPI):
    url = f'{ParsianAPI.BASE_URL}/pec/api/Issuer/HashCard'
    method = 'POST'
    endpoint_key = 'hashPan'
    error_message = 'ParsianHashPan'

    @measure_time_cm(metric='abc_parsian_debit_card_hash_pan')
    def request(self, pan: str) -> str:
        try:
            resp = self._request(json={'CardNumber': pan})
        except ThirdPartyError as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        result = resp.json().get('GetHashCardsRequest')
        if not result:
            report_event(f'{self.error_message}: invalid response', extras={'data': resp.json()})
            raise ThirdPartyError(f'{self.error_message}: invalid response')

        card_number = result.get('CardNumber')
        if not card_number or card_number != pan:
            report_event(f'{self.error_message}: invalid response', extras={'data': resp.json()})
            raise ThirdPartyError(f'{self.error_message}: invalid response')

        hashed_pan = result.get('HashCode')
        if not hashed_pan:
            report_event(f'{self.error_message}: invalid response', extras={'data': resp.json()})
            raise ThirdPartyError(f'{self.error_message}: invalid response')

        return hashed_pan


class DebitCardOTPVerifyAPI(ParsianAPI):
    url = f'{ParsianAPI.BASE_URL}/pec/api/issuer/ActiveCardWithOTP'
    method = 'POST'
    endpoint_key = 'otpVerify'
    error_message = 'ParsianOtpVerify'

    @measure_time_cm(metric='abc_parsian_debit_card_otp_verify')
    def request(self, pan: str, code: str) -> bool:
        try:
            hashed_pan = DebitCardHashPanAPI().request(pan=pan)
            resp = self._request(json={'CardNumberHash': hashed_pan, 'OTPCode': code})
        except ThirdPartyError as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise ThirdPartyError(f'{self.error_message}: Fail to connect server') from e

        return resp.json().get('IsSuccess', False)


class DebitCardSuspendAPI(ParsianAPI):
    url = f'{ParsianAPI.BASE_URL}/pec/api/Issuer/SuspendChildCard'
    method = 'POST'
    endpoint_key = 'suspend'
    error_message = 'ParsianSuspend'

    # TODO: fill these values
    REASON_CODE = 1
    DESCRIPTION = 'درخواست مشتری'

    @measure_time_cm(metric='abc_parsian_debit_card_suspend')
    def request(self, pan: str) -> bool:
        try:
            resp = self._request(
                json={
                    'ChildCardNumber': pan,
                    'ParentCardNumber': ParsianAPI.PARENT_CARD_NUMBER,
                    'SuspendIdentifier': self.REASON_CODE,
                    'Description': self.DESCRIPTION,
                }
            )
        except (ClientError, ThirdPartyError) as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise ThirdPartyError('failed to suspend card.') from e

        return resp.json().get('IsSuccess', False)
