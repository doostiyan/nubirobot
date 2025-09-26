from dataclasses import dataclass
from typing import IO, Optional, Union

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from requests import Timeout
from rest_framework import status

from exchange.base.logging import log_event, metric_incr, report_exception
from exchange.base.models import Settings
from exchange.integrations.auto_kyc_rest_wrapper import AutoKycRestWrapper
from exchange.integrations.models import APICallLog


class FinnotechAPIError(ValueError):
    pass


class JibitAPIError(ValueError):
    pass


def get_jibit_verification_token():
    return settings.JIBIT_KYC_TOKEN


def restore_user_to_level1(user, action='both') -> bool:
    try:
        from exchange.accounts.models import User
        if user.user_type == User.USER_TYPES.level2:
            user.user_type = User.USER_TYPES.level1
            user.save(update_fields=['user_type'])
        vp = User.get_verification_profile(user)
        update_fields = []
        if action in ['liveness', 'both'] and vp.identity_liveness_confirmed:
            vp.identity_liveness_confirmed = False
            update_fields.append('identity_liveness_confirmed')
        if update_fields:
            vp.save(update_fields=update_fields)
        return True
    except:
        report_exception()
        return False


class AutoKYC:
    @dataclass
    class AutoKYCUserData:
        user: Optional['User']
        national_code: Optional[str]
        national_serial_number: Optional[str]
        shamsi_birth_date: Optional[str]
        live_face: Optional[IO[bytes]]
        liveness_clip: Optional[IO[bytes]]
        error: Optional[dict]

    @dataclass
    class AutoKYCApiCallResult:
        json_result: Optional[dict]
        status_code: int
        error: Optional[dict]

    def __init__(self):
        self.auto_kyc_rest_wrapper_instance = AutoKycRestWrapper(timeout_seconds=30)
        self.INCOMPLETE_USER_INFO_MESSAGE = 'اطلاعات کاربر ناقص است _ '
        self.CONNECTION_PROBLEM_MESSAGE = 'خطا در ارسال درخواست _ '

        self.FILE_NOT_FOUND_RESULT = {
            'result': False,
            'message': 'فایل مورد نظر پیدا نشد.',
            'confidence': 50,
            'apiresponse': {
                'liveness': {
                    'error': {
                        'message': 'فایل های پیوستی ناقص هستند.',
                    },
                }
            },
        }
        self.INCOMPLETE_USER_INFO_RESULT = {
            'result': False,
            'message': 'اطلاعات کاربر ناقص است.',
            'confidence': 50,
            'apiresponse': {
                'liveness': {
                    'error': {
                        'message': '',
                    },
                }
            },
        }
        self.INVALID_USER_INFO_RESULT = {
            'result': False,
            'message': 'اطلاعات وارد شده نامعتبر است.',
            'confidence': 100,
            'apiresponse': {
                'error': {
                    'message': '',
                },
            },
        }
        self.TIMEOUT_RESULT = {
            'result': False,
            'message': 'دریافت پاسخ بیش از حد به طول انجامیده است.',
            'confidence': 50,
            'apiresponse': {
                'liveness': {
                    'error': {
                        'message': '',
                    },
                }
            },
        }
        self.CONNECTION_PROBLEM_RESULT = {
            'result': False,
            'message': 'ارسال درخواست با مشکل مواجه شده است.',
            'confidence': 50,
            'apiresponse': {
                'liveness': {
                    'error': {
                        'message': '',
                    },
                }
            },
        }
        self.GENERAL_ERROR_RESULT = {
            'result': False,
            'message': 'خطایی رخ داده است',
            'confidence': 50,
            'apiresponse': {
                'liveness': {
                    'error': ''
                }
            },
        }
        self.AUTHENTICATION_FAILURE_RESULT = {
            'result': False,
            'message': 'هویت کاربر مورد تائید نیست',
            'confidence': 50,
            'apiresponse': {
                'liveness': dict()
            },
        }
        self.LIVENESS_NOT_APPROVED_RESULT = {
            'result': False,
            'message': 'وضعیت حیات کاربر مورد تائید نیست',
            'confidence': 50,
            'apiresponse': {
                'liveness': dict()
            },
        }
        self.OK_RESULT = {
            'result': True,
            'message': 'ok',
            'confidence': 100,
            'apiresponse': {
                'liveness': dict()
            },
        }
        self.API_CALL_FAILURES_MESSAGES = {
            self.TIMEOUT_RESULT['message'],
            self.CONNECTION_PROBLEM_RESULT['message'],
            self.GENERAL_ERROR_RESULT['message']
        }

    def check_user_liveness(self, verification_request: 'VerificationRequest', retry: int = 0) -> dict:
        """This method uses jibit API to verify user liveness - V2
        Base url: 'https://napi.jibit.ir/alpha-nobitex/api/v2
        Sample return value in error situation:
        Including an error code and an error message. If there's an error the data field is
        either empty or contains more details about the error.
        {
            "errorCode": 102,
            "errorMessage": "",
            "data": ""
        }

        Sample return value in ok situation:
        {
            "verification_result": {
                "errorCode": "",
                "errorMessage": "",
                "data": {
                    "result": true,
                    "details": {
                        "distance": 0.95465468484,
                        "similarity": 100
                    },
                    "duration": 0.95465654654
                }
            },
            "liveness_result": {
                "errorCode": "",
                "errorMessage": "",
                "data": {
                    "FaceAnchor": "3 of 5 anchor completed",
                    "Duration": 0.225465486,
                    "Score": "0.001546848",
                    "Guide": "The score lower than threshold is live and higher that threshold is spoof",
                    "State": "true"
                }
            }
        }
        """

        user_data = self._get_user_data(verification_request)
        if user_data.error:
            return user_data.error
        user = user_data.user

        api_call_result = self._call_auto_kyc_api(user_data)
        error = api_call_result.error
        json_result = api_call_result.json_result
        status_code = api_call_result.status_code
        if error:
            self._log_api_calls(user, verification_request, error, retry, status_code)
            return error

        log_event(f'Check user liveness - status_code: {status_code}', level='INFO',
                  category='history', module='apicall', runner='admin', details=json_result)
        has_error, error_message = \
            self.auto_kyc_rest_wrapper_instance.extract_auto_kyc_error_message(json_result, status_code)
        if has_error:
            error_tp = self._identify_error_type(error_message)
            return self._handle_verification_error(
                user=user,
                tp=error_tp,
                other_info=error_message,
                retry=retry,
                verification_request=verification_request,
                status_code=status_code,
            )

        verification_result, liveness_result = self.auto_kyc_rest_wrapper_instance.extract_auto_kyc_results(json_result)
        if not verification_result:
            return self._handle_verification_error(user=user, tp='AUTHENTICATION_FAILURE_RESULT',
                                                   other_info=json_result, retry=retry,
                                                   verification_request=verification_request, status_code=status_code)
        if not liveness_result:
            return self._handle_verification_error(user=user, tp='LIVENESS_NOT_APPROVED_RESULT', other_info=json_result,
                                                   retry=retry, verification_request=verification_request,
                                                   status_code=status_code)

        user.do_verify_liveness_alpha()
        self.OK_RESULT['apiresponse']['liveness'] = json_result
        self._log_api_calls(user, verification_request, self.OK_RESULT, retry, status_code)
        metric_incr(f'metric_kyc_verification__autokyc_success')
        return self.OK_RESULT

    def _get_user_data(self, verification_request: 'VerificationRequest') -> AutoKYCUserData:
        user = verification_request.user
        national_code = user.national_code
        national_serial_number = user.national_serial_number
        shamsi_birth_date = user.birthday_shamsi
        try:
            main_image = verification_request.documents.get(tp=3)  # kyc_main_image
            gif = verification_request.documents.get(tp=4)  # kyc_image
            live_face = open(main_image.disk_path, 'rb')
            liveness_clip = open(gif.disk_path, 'rb')
        except (ObjectDoesNotExist, FileNotFoundError):
            return self.AutoKYCUserData(None, None, None, None, None, None, self.FILE_NOT_FOUND_RESULT)
        except Exception as e:
            report_exception()
            self.INCOMPLETE_USER_INFO_RESULT['apiresponse']['liveness']['error']['message'] = \
                self.INCOMPLETE_USER_INFO_MESSAGE + str(e)
            return self.AutoKYCUserData(None, None, None, None, None, None, self.INCOMPLETE_USER_INFO_RESULT)
        return self.AutoKYCUserData(
            user, national_code, national_serial_number, shamsi_birth_date, live_face, liveness_clip, None
        )

    def _identify_error_type(self, error_message):
        error_type = 'GENERAL_ERROR_RESULT'
        if 'اطلاعات وارد شده نامعتبر است' in error_message:
            error_type = 'INVALID_USER_INFO_RESULT'
        return error_type

    def _call_auto_kyc_api(self, user_data: AutoKYCUserData) -> AutoKYCApiCallResult:
        liveness_url = self.auto_kyc_rest_wrapper_instance.liveness_endpoint
        try:
            liveness_threshold = Settings.get_cached_json('auto_kyc_liveness_threshold', default=0.9)
            # For now both serial and birth_date have value but in future either one can be null
            # and Jibit/Alpha will receive either ssn and birth_date or ssn and serial
            payload = {
                'ssn': user_data.national_code,
                'serial': user_data.national_serial_number,
                'birth_date': user_data.shamsi_birth_date,
                'liveness_threshold': liveness_threshold,  # is optional for now
            }
            files = {'live_face': user_data.live_face, 'liveness_clip': user_data.liveness_clip}
            json_result, status_code = self.auto_kyc_rest_wrapper_instance.send_https_request(liveness_url, payload,
                                                                                              files)
        except Timeout as e:
            report_exception()
            self.TIMEOUT_RESULT['apiresponse']['liveness']['error']['message'] = str(e)
            return self.AutoKYCApiCallResult(None, status.HTTP_408_REQUEST_TIMEOUT, self.TIMEOUT_RESULT)
        except Exception as e:
            report_exception()
            self.CONNECTION_PROBLEM_RESULT['apiresponse']['liveness']['error']['message'] = \
                self.CONNECTION_PROBLEM_MESSAGE + str(e)
            return self.AutoKYCApiCallResult(None, status.HTTP_400_BAD_REQUEST, self.CONNECTION_PROBLEM_RESULT)
        return self.AutoKYCApiCallResult(json_result, status_code, None)

    def _handle_verification_error(self, user, tp: str, other_info: Union[str, dict], retry: int,
                                   verification_request, status_code) -> dict:
        restore_user_to_level1(user, 'liveness')
        error = dict()
        if tp == 'GENERAL_ERROR_RESULT':
            self.GENERAL_ERROR_RESULT['apiresponse']['liveness']['error'] = other_info
            error = self.GENERAL_ERROR_RESULT
        elif tp == 'AUTHENTICATION_FAILURE_RESULT':
            self.AUTHENTICATION_FAILURE_RESULT['apiresponse']['liveness'] = other_info
            error = self.AUTHENTICATION_FAILURE_RESULT
        elif tp == 'INVALID_USER_INFO_RESULT':
            self.INVALID_USER_INFO_RESULT['apiresponse']['error']['message'] = other_info
            error = self.INVALID_USER_INFO_RESULT
        elif tp == 'LIVENESS_NOT_APPROVED_RESULT':
            self.LIVENESS_NOT_APPROVED_RESULT['apiresponse']['liveness'] = other_info
            error = self.LIVENESS_NOT_APPROVED_RESULT
        self._log_api_calls(user=user, verification_request=verification_request, response=error, retry=retry,
                            status_code=status_code)
        metric_incr(f'metric_kyc_verification__autokyc_failure')
        return error

    def failed_calling_api(self, api_call_result: dict) -> bool:
        return api_call_result.get('message', '') in self.API_CALL_FAILURES_MESSAGES

    def _log_api_calls(self, user, verification_request, response: dict, retry: int, status_code: int):

        url = self.auto_kyc_rest_wrapper_instance.base_url + self.auto_kyc_rest_wrapper_instance.liveness_endpoint
        request_details = {
            'main_image_filename': str(verification_request.documents.get(tp=3).filename),  # kyc_main_image,
            'gif_filename': str(verification_request.documents.get(tp=4).filename),  # kyc_image,
        }
        APICallLog.objects.create(
            content_object=user,
            retry=retry,
            api_url=url,
            request_details=request_details,
            response_details=response,
            status=APICallLog.STATUS.failure,
            status_code=status_code,
            provider=APICallLog.PROVIDER.alpha,
            service=APICallLog.SERVICE.liveness,
        )
