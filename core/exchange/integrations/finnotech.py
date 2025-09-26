import base64
from typing import Dict, Optional, Tuple
from urllib.parse import urljoin

import requests

from exchange import settings
from exchange.base.decorators import measure_time_cm
from exchange.base.logging import metric_incr, report_event, report_exception
from exchange.base.models import Settings
from exchange.base.normalizers import compare_full_names, compare_names
from exchange.integrations.base import VerificationClientBase
from exchange.integrations.exceptions import (
    CardToIbanError,
    DeadLivingStatus,
    FinnotechAPIError,
    InactiveCard,
    InactiveIBAN,
    InvalidBirthDate,
    InvalidCard,
    InvalidIBAN,
    InvalidMobile,
    InvalidNationalCode,
    MismatchedCard,
    MismatchedIBAN,
    NotFound,
    UnknownCardQueryError,
    UnknownLivingStatus,
)
from exchange.integrations.types import (
    CardToIbanAPICallResultV2,
    IdentityVerificationClientResult,
    VerificationAPIProviders,
)

FINNOTECH_API_ACCESS_TOKEN_KEY = 'finnotech_api_access_token'
FINNOTECH_API_REFRESH_TOKEN_KEY = 'finnotech_api_refresh_token'


def get_finnotech_access_token():
    # TODO: Fallback value is considered for handling empty token issues when new token changes
    #  is deployed for the first time. It should be removed when service stability is proven
    access_token = Settings.get(FINNOTECH_API_ACCESS_TOKEN_KEY, '')
    if access_token is None or access_token == '':
        return Settings.get('finnotech_verification_api_token')

    return access_token


class FinnotechTokenAPI:
    url = 'https://api.finnotech.ir/dev/v2/oauth2/token'
    scopes = [
        'oak:nid-verification:get',
        'oak:iban-inquiry:get',
        'card:information:get',
        'card:shahkar:get',
        'facility:card-to-iban:get',
        'facility:finnotext:post',
        'facility:finnotext-inquiry:get',
        'facility:finnotext-otp:post',
    ]

    @classmethod
    def _get_basic_auth_header(cls):
        header_value = base64.b64encode(bytes('nobitex:' + settings.FINNOTECH_CLIENT_SECRET, 'utf8')).decode()
        return {'Authorization': f'Basic {header_value}'}

    @classmethod
    @measure_time_cm(metric='finnotech_getToken')
    def get_token(cls):
        """
        Retrieves an access token from the Finnotech API.

        Document: https://finnotech.ir/doc/boomrang-get-clientCredential-token.html

        Sample API response:
        {
            'result': {
                'value': 'eyJhbGciOiJIUzI1NiIsInR5cCI6...',
                'scopes': [
                    'facility:finnotext:post'
                ],
                'lifeTime': 864000000,
                'creationDate': '13970730111355',
                'refreshToken': 'U5ltxeu3pnbotPDG9q...',
            },
            'status': 'DONE'
        }
        """
        try:
            response = requests.post(
                cls.url,
                headers=cls._get_basic_auth_header(),
                json={
                    'grant_type': 'client_credentials',
                    'nid': settings.FINNOTECH_CLIENT_NID,
                    'scopes': ','.join([scope for scope in cls.scopes]),
                },
                timeout=30,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            report_exception()
            return {'result': False}

        return cls._save_tokens(response)

    @classmethod
    @measure_time_cm(metric='finnotech_refreshToken')
    def refresh_token(cls):
        """Renew Finnotech verification API token. The previous token and refresh token are read
        from Settings table and if the refresh succeeds, saved token and refresh token are updated.

        Document: https://docs.finnotech.ir/boomrang-refresh-token.html
        """
        try:
            response = requests.post(
                cls.url,
                headers=cls._get_basic_auth_header(),
                json={
                    'grant_type': 'refresh_token',
                    'token_type': 'CLIENT-CREDENTIAL',
                    'refresh_token': Settings.get(FINNOTECH_API_REFRESH_TOKEN_KEY),
                },
                timeout=30,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException:
            report_exception()
            return {'result': False}

        return cls._save_tokens(response)

    @classmethod
    def _save_tokens(cls, response):
        """Sample return value:
        {
            result: True,
            accesstoken: "eyJhbGciOiJIUzI1NiIYVI3yhZEeXhNc05MZkdCM2dDV...",
            refreshtoken: "sI2t91Bm7zwuORlHDIcdVAw4Ewal7a33KDquF7SJY...",
        }"""

        json_result = response.json()
        if json_result.get('status', '').upper() != 'DONE':
            report_exception()
            return {'result': False}

        result = json_result.get('result', {})
        access_token = result.get('value')
        refresh_token = result.get('refreshToken')

        if not access_token or not refresh_token:
            return {'result': False}

        # Update tokens in Settings
        Settings.set(FINNOTECH_API_ACCESS_TOKEN_KEY, access_token)
        Settings.set(FINNOTECH_API_REFRESH_TOKEN_KEY, refresh_token)

        # TODO: Just for backward compatibility with admin project finnotech key.
        #  We should remove updating old keys after admin project updated
        Settings.set('finnotech_verification_api_token', access_token)
        Settings.set('finnotech_verification_refresh_token', refresh_token)

        return {
            'result': True,
            'accesstoken': access_token,
            'refreshtoken': refresh_token,
        }


class FinnotechVerificationClient(VerificationClientBase):
    name = 'finnotech'
    base_url = 'https://apibeta.finnotech.ir/'

    def get_token(self):
        return get_finnotech_access_token()

    def request(self, url: str, data: Optional[Dict] = None):
        result = None
        try:
            result = requests.get(
                urljoin(self.base_url, url),
                params=data,
                headers={
                    'Authorization': 'Bearer ' + self.get_token(),
                },
                timeout=30,
            )

            json_result = result.json()
            if json_result.get('message') == 'invalid token':
                raise FinnotechAPIError('InvalidToken')
        except requests.exceptions.RequestException as ex:
            raise FinnotechAPIError('ConnectionError') from ex

        if not json_result or ('result' not in json_result and 'error' not in json_result):
            raise FinnotechAPIError('HTTPError', result.status_code)

        return result

    def get_user_identity(self, user) -> IdentityVerificationClientResult:
        """This method uses Finnotech API to verify user identity information. All identity fields, including
        user first and last name, national code, and birthday are required. Identity is confirmed if all of
        the given fields has a minimum required similarity level to the real information returned from  API.

        Scope: oak:nid-verification:get
        Document: https://docs.finnotech.ir/oak-nidVerification.html

        Sample return value:
        {
        "result": true,
        "message": "ok",
        "confidence": 100,
        "apiresponse": {
            "trackId": "57a52048-6cc9-4a71-b1a2-b21ad25650e8",
            "result": {
            "nationalCode": "2980987654",
            "birthDate": "1363/06/31",
            "firstName": "محمد",
            "firstNameSimilarity": 100,
            "lastName": "حسنی کبوترخانی",
            "lastNameSimilarity": 100,
            "fullName": "محمد حسنی کبوترخانی",
            "fullNameSimilarity": 100,
            "deathStatus": "زنده"
            },
            "status": "DONE"
        }
        }
        """

        father_name = None
        birth_date_str = user.birthday_shamsi
        data = {
            'nationalCode': user.national_code,
            'birthDate': birth_date_str,
            'fullName': user.get_full_name(),
            'firstName': user.first_name,
            'lastName': user.last_name,
            'fatherName': father_name,
        }

        api_result = self.request('/oak/v2/clients/nobitex/nidVerification', data)
        json_result = api_result.json()

        # Check API call status
        if api_result.status_code == 400:
            error_message = json_result.get('error', {}).get('message')
            error_message = (error_message or '').strip()
            if error_message == 'کد ملی یا تاریخ تولد اشتباه است':
                raise InvalidNationalCode(api_response=json_result, provider=VerificationAPIProviders.FINNOTECH.value)
            if error_message == 'invalid birthdate':
                raise InvalidBirthDate(api_response=json_result, provider=VerificationAPIProviders.FINNOTECH.value)

        if api_result.status_code != 200 or 'result' not in json_result:
            raise FinnotechAPIError('NoResult', api_result.status_code)

        api_result = json_result['result']

        if json_result.get('responseCode') == 'FN-OHKZ-20003840373':
            raise InvalidNationalCode(api_response=json_result, provider=VerificationAPIProviders.FINNOTECH.value)

        if 'deathStatus' not in api_result:
            raise UnknownLivingStatus(api_response=json_result, provider=VerificationAPIProviders.FINNOTECH.value)
        if api_result['deathStatus'] != 'زنده':
            raise DeadLivingStatus(api_response=json_result, provider=VerificationAPIProviders.FINNOTECH.value)

        if not any(['lastNameSimilarity' in api_result, 'fullNameSimilarity' in api_result]):
            raise FinnotechAPIError('NoSimilarity', api_result.status_code)

        result = IdentityVerificationClientResult(provider=VerificationAPIProviders.FINNOTECH, api_response=json_result)
        if 'firstNameSimilarity' in api_result:
            result.first_name_similarity = api_result['firstNameSimilarity']
        if 'lastNameSimilarity' in api_result:
            result.last_name_similarity = api_result['lastNameSimilarity']
        if 'fullNameSimilarity' in api_result:
            result.full_name_similarity = api_result['fullNameSimilarity']
        if 'fatherNameSimilarity' in api_result:
            result.father_name_similarity = api_result['fatherNameSimilarity']

        return result

    def is_national_code_owner_of_mobile_number(self, national_code: str, mobile: str) -> Tuple[bool, dict]:
        """This method uses Finnotech Shahkar API to check if the owner of mobile is the national code user provide.
        Return value is a dict having a result key that show if the mobile and national code matches. If there is
        any error in connecting to remote API, the result is undefined, so an exception of FinnotechAPIError type
        is raised.

        Scope: facility:shahkar:get
        Document: request manual doc file on nobitex-finnotech business whatsapp group

        Sample return value:
        {
        "result": true,
        "message": "ok",
        "apiresponse": {
            "trackId": "b14bade6-77a3-4d62-9f5a-9a46af700dce",
            "result": {
            "isValid": true
            },
            "status": "DONE"
        }
        }
        """
        data = {
            'nationalCode': national_code,
            'mobile': mobile,
        }
        api_result = self.request('/mpg/v2/clients/nobitex/shahkar/verify', data)
        json_result = api_result.json()
        if json_result.get('responseCode') == 'FN-MGFH-40000030057':
            raise InvalidMobile('responseCode', self.name, json_result['error']['message'])
        if api_result.status_code != 200 or 'result' not in json_result:
            raise FinnotechAPIError('NoResult', api_result.status_code)

        result = json_result['result']
        return result['isValid'], json_result

    def is_user_owner_of_iban(self, first_name: str, last_name: str, iban: str) -> Tuple[bool, Dict]:
        """This method use Finnotech api to check if owner of SHABA number is the user.
        Get data from api and check api fullname and database fullname based on shaba number.
        sometimes api put two space between first name and last name and sometimes put one.
        because of this, i remove all space in api fullname and database fullname and then compare with each other.

        Scope: oak:iban-inquiry:get
        Document: https://docs.finnotech.ir/oak-ibanInquiry.html

        Sample return value:
        {
            "result": True,
            "message": "ok",
            "confidence": 100,
            "apiresponse": {
                "trackId": "e716bf23-6e04-4b78-97d7-09d0c3c88b74",
                "result": {
                    "IBAN": "IR460170000000346416632004",
                    "bankName": "بانک ملی ایران",
                    "deposit": "0346419332494",
                    "depositDescription": "حساب فعال است",
                    "depositComment": "",
                    "depositOwners": [
                        {
                        "firstName": "محمد",
                        "lastName": "حسنی  "
                        }
                    ],
                    "depositStatus": "02",
                    "errorDescription": "بدون خطا"
                },
                "status": "DONE"
            }
        }
        """
        data = {
            'iban': iban,
        }

        api_result = self.request('/oak/v2/clients/nobitex/ibanInquiry', data)
        json_result = api_result.json()

        if json_result.get('message') == 'invalid token':
            raise FinnotechAPIError('InvalidToken', api_result.status_code)
        if json_result.get('error', {}).get('message') == 'شماره شبا اشتباه است':
            raise InvalidIBAN(api_response=json_result, provider=self.name)

        if api_result.status_code != 200 or 'result' not in json_result:
            raise FinnotechAPIError('NoResult', api_result.status_code)

        result = json_result['result']
        if result['depositStatus'] not in ['02', '2']:
            raise InactiveIBAN(api_response=json_result, provider=self.name)

        owner_found = False
        for deposit_owner in result['depositOwners']:
            if result['IBAN'][5:7] == '18':
                # Tejarat bank sometimes return full name of accounts in first name
                full_name = ' '.join([first_name, last_name]).strip()
                if compare_full_names(full_name, deposit_owner['firstName']):
                    owner_found = True
                    break
            if compare_names(first_name, last_name, deposit_owner['firstName'], deposit_owner['lastName']):
                owner_found = True
                break

        if not owner_found:
            raise MismatchedIBAN(api_response=json_result, provider=self.name)

        return True, json_result

    def is_user_owner_of_bank_card(self, full_name: str, card_number: str) -> Tuple[bool, Dict]:
        """This method use Finnotech api to verify if owner of card number is the user.
        Get data from api and check api fullname and database fullname based on bank card number.
        sometimes api put two space between first name and last name and sometimes put one.
        because of this, i remove all space in api fullname and database fullname and then compare with each other.

        Scope: card:information:get
        Document: https://docs.finnotech.ir/card-information.html
        Note: This method must be called from authorized IPs (i.e. directly from server)

        Sample return value:
        {
            "result": True,
            "message": "ok",
            "confidence": 100,
            "apiresponse": {
                "trackId": "8aa6ae3d-ec17-4436-a09d-3ba8d3a5a4dc",
                "result": {
                    "destCard": "6037-99xx-xxxx-8812",
                    "name": "محمد حسنی",
                    "result": "0",
                    "description": "موفق",
                    "doTime": "1398/04/12 15:33:20"
                },
                "status": "DONE"
            }
        }
        """
        api_result = self.request(f'/mpg/v2/clients/nobitex/cards/{card_number}?sandbox=true')
        json_result = api_result.json()
        if json_result.get('message') == 'invalid token':
            raise FinnotechAPIError('InvalidToken', api_result.status_code)

        if json_result.get('error', {}).get('message') in [
            'شماره کارت اشتباه است',
            'شماره ی کارت نامعتبر است',
        ]:
            raise InvalidCard(api_response=json_result, provider=self.name)

        if json_result.get('responseCode') == 'FN-MGFH-40000130125':
            raise InvalidCard(api_response=json_result, provider=self.name)

        if api_result.status_code != 200 or 'result' not in json_result:
            raise FinnotechAPIError('NoResult', api_result.status_code)

        result = json_result['result']
        api_call_status = result.get('result', '-1')
        if api_call_status == '78':
            raise InvalidCard(api_response=json_result, provider=self.name)
        if api_call_status == '135':
            raise InactiveCard(api_response=json_result, provider=self.name)
        if api_call_status != '0':
            raise UnknownCardQueryError(api_response=json_result, provider=self.name)

        if not compare_full_names(full_name, result['name']):
            raise MismatchedCard(api_response=json_result, provider=self.name)

        return True, json_result

    def convert_card_number_to_iban(self, card_number: str) -> CardToIbanAPICallResultV2:
        """This method use Finnotech api to convert card number of one user to iban.

        Scope: facility:card-to-iban:get
        Document: https://docs.finnotech.ir/facility-card-to-iban-v2.html

        Sample return value:
        {
            'trackId': 'trackId',
            'result': {
                'IBAN': 'IR500160000000300000000001',
                'bankName': 'بانک کشاورزی ',
                'deposit': '0300000010001',
                'card': '6037000020090110',
                'depositStatus': '02',
                'depositOwners': 'علی آقایی'
            },
            'status': 'DONE'
        }
        """
        metric_name = self.name + 'ConvertCardNumberToIban'
        api_result = self.request(f'/facility/v2/clients/nobitex/cardToIban?version=2&card={card_number}')
        json_result = api_result.json()
        status_code = api_result.status_code
        if 'status' in json_result and json_result['status'] == 'FAILED':
            metric_incr(f'metric_integrations_errors__{metric_name}_{status_code}')
            if 'responseCode' in json_result:
                msg = json_result['error']['message']
                if json_result['responseCode'] == 'FN-FYFH-40000140353':
                    raise FinnotechAPIError('UnSupportedCard', api_result.status_code)

                if json_result['responseCode'] in ('FN-FYJT-50000140367', 'FN-FYJT-50000140366'):
                    raise FinnotechAPIError('BankUnavailable', api_result.status_code)

                if json_result['responseCode'] in (
                    'FN-FYJT-40000140334',
                    'FN-FYJT-40000130125',
                    'FN-FYJT-40000140626',
                    'FN-FYJT-40000140354',
                    'FN-FYJT-40000140627',
                ):
                    raise InvalidCard(api_response=json_result, provider=self.name, msg=msg)
                if json_result['responseCode'] == 'FN-FYJT-40400140385':
                    raise NotFound(api_response=json_result, provider=self.name, msg=msg)

            raise FinnotechAPIError('NoResponseCode', api_result.status_code)

        if status_code != 200 or 'result' not in json_result:
            metric_incr(f'metric_integrations_errors__{metric_name}_{status_code}')
            raise FinnotechAPIError('NoResult', api_result.status_code)

        deposit_descriptions = {
            '2': 'حساب فعال است',
            '3': ' حساب مسدود با قابلیت واریز',
            '4': 'حساب مسدود بدون قابلیت واریز',
            '5': ' حساب راکد است',
            '6': ': بروز خطادر پاسخ دهی , شرح خطا در فیلد توضیحات است',
            '7': 'سایر موارد',
        }

        result = json_result['result']

        try:
            if 'depositStatus' in result and 'depositDescription' not in result:
                key = result['depositStatus'].lstrip('0')
                result.update({'depositDescription': deposit_descriptions[key]})
                json_result['result'] = result
        except KeyError:
            report_event('ConvertCardNumberToIban', extras={'api_response': result})

        if 'depositStatus' not in result or result['depositStatus'] not in ['02', '2']:
            err_msg = (
                result['depositDescription']
                if result['depositDescription'] and int(result['depositStatus']) in range(3, 6)
                else 'حساب بانکی شما فعال نیست.'
            )
            raise CardToIbanError(
                provider=self.name,
                api_response=json_result,
                msg=err_msg,
            )

        return CardToIbanAPICallResultV2(
            provider=VerificationAPIProviders.FINNOTECH,
            api_response=json_result,
            deposit=result['deposit'],
            iban=result['IBAN'],
            owners=result['depositOwners'].split('/'),
        )
