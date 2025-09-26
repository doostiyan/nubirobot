import datetime
import os
import uuid
from unittest.mock import ANY, MagicMock, patch

from django.test import TestCase

from exchange.accounts.models import UploadedFile, User, VerificationRequest
from exchange.accounts.verificationapi import AutoKYC
from exchange.integrations.models import APICallLog
from tests.accounts.autokyc_api_call_mocks import (
    AUTOKYC_CLIENT_EXPECTED_RESPONSES,
    NEW_ALPHA_LIVENESS_APICALL_RESPONSE_MOCK,
)


class OldLivenessMockResponse:
    def __init__(self, tp='success'):
        self.status_code = 200
        if tp == 'success':
            self.json_data = {'verification_result': True, 'liveness_result': True}
        elif tp == 'not_verification':
            self.json_data = {'verification_result': False, 'liveness_result': True}
        elif tp == 'not_liveness':
            self.json_data = {'verification_result': True, 'liveness_result': False}
        elif tp == 'status_400':
            self.status_code = 400
            self.json_data = {'message': 'خطای تستی'}

    def json(self):
        return self.json_data


class VerificationTest(TestCase):
    NEW_LIVENESS_RESPONSE_MOCK = NEW_ALPHA_LIVENESS_APICALL_RESPONSE_MOCK
    EXPECTED_RESPONSE = AUTOKYC_CLIENT_EXPECTED_RESPONSES

    def create_fake_data(self):
        ufile_main_image = UploadedFile(filename=uuid.uuid4(), user=self.user, tp=UploadedFile.TYPES.kyc_main_image)
        with open(ufile_main_image.disk_path, 'w+') as destination:
            destination.write('main_image')
        ufile_main_image.save()
        self.addCleanup(os.remove, ufile_main_image.disk_path)

        ufile_image = UploadedFile(filename=uuid.uuid4(), user=self.user, tp=UploadedFile.TYPES.kyc_image)
        with open(ufile_image.disk_path, 'w+') as destination:
            destination.write('gif')
        ufile_image.save()
        self.addCleanup(os.remove, ufile_image.disk_path)

        ufile_video = UploadedFile(filename=uuid.uuid4(), user=self.user, tp=UploadedFile.TYPES.kyc_video)
        with open(ufile_video.disk_path, 'w+') as destination:
            destination.write('video')
        ufile_video.save()
        self.addCleanup(os.remove, ufile_video.disk_path)

        self.req = VerificationRequest.objects.create(
            user=self.user,
            tp=VerificationRequest.TYPES.auto_kyc,
            explanations='test',
        )

        self.req.documents.add(ufile_image)
        self.req.documents.add(ufile_main_image)
        self.req.documents.add(ufile_video)

    @classmethod
    def mock_liveness(cls, tp='success'):
        response_mock = MagicMock()
        response_mock.status_code = 400 if tp == 'status_400' else 200
        response_mock.json.return_value = cls.NEW_LIVENESS_RESPONSE_MOCK.get(tp)
        return response_mock

    def setUp(self):
        self.user = User.objects.get(pk=201)

        self.user.user_type = User.USER_TYPES.level1
        self.user.address = 'تست آباد خیابان آزمایش کوچه امتحان پلاک ۱۰'
        self.user.city = 'تست آباد'
        self.user.phone = '12345678'
        self.user.save()

        vp = self.user.get_verification_profile()
        vp.mobile_confirmed = True
        vp.mobile_identity_confirmed = True
        vp.email_confirmed = True
        vp.identity_confirmed = True
        vp.address_confirmed = True
        vp.bank_account_confirmed = True
        vp.selfie_confirmed = False
        vp.save()

        self.create_fake_data()
        self.auto_kyc_instance = AutoKYC()

    @patch('exchange.integrations.auto_kyc_rest_wrapper.requests')
    def test_check_user_liveness(self, mock):
        mock.post.return_value = self.mock_liveness('success')
        assert self.auto_kyc_instance.check_user_liveness(self.req) == self.EXPECTED_RESPONSE['success']
        assert APICallLog.objects.filter(response_details__message='ok').count() == 1

        mock.post.return_value = self.mock_liveness('invalid_data')
        assert self.auto_kyc_instance.check_user_liveness(self.req) == self.EXPECTED_RESPONSE['invalid_data']
        assert APICallLog.objects.filter(response_details__message='اطلاعات وارد شده نامعتبر است.').count() == 1

        mock.post.return_value = self.mock_liveness('status_200_but_error')
        assert self.auto_kyc_instance.check_user_liveness(self.req) == self.EXPECTED_RESPONSE['status_200_but_error']
        assert APICallLog.objects.filter(response_details__message='خطایی رخ داده است').count() == 1

        mock.post.return_value = self.mock_liveness('status_200_but_liveness_error')
        assert (
            self.auto_kyc_instance.check_user_liveness(self.req)
            == self.EXPECTED_RESPONSE['status_200_but_liveness_error']
        )
        assert APICallLog.objects.filter(response_details__message='خطایی رخ داده است').count() == 2

        mock.post.return_value = self.mock_liveness('not_verification')
        assert self.auto_kyc_instance.check_user_liveness(self.req) == self.EXPECTED_RESPONSE['not_verification']
        assert APICallLog.objects.filter(response_details__message='خطایی رخ داده است').count() == 2
        assert APICallLog.objects.filter(response_details__message='هویت کاربر مورد تائید نیست').count() == 1

        mock.post.return_value = self.mock_liveness('not_liveness')
        assert self.auto_kyc_instance.check_user_liveness(self.req) == self.EXPECTED_RESPONSE['not_liveness']
        assert APICallLog.objects.filter(response_details__message='خطایی رخ داده است').count() == 2
        assert APICallLog.objects.filter(response_details__message='هویت کاربر مورد تائید نیست').count() == 1
        assert APICallLog.objects.filter(response_details__message='وضعیت حیات کاربر مورد تائید نیست').count() == 1

        mock.post.return_value = self.mock_liveness('status_400')
        assert self.auto_kyc_instance.check_user_liveness(self.req) == self.EXPECTED_RESPONSE['status_400']
        assert APICallLog.objects.filter(response_details__message='خطایی رخ داده است').count() == 3
        assert APICallLog.objects.filter(response_details__message='هویت کاربر مورد تائید نیست').count() == 1
        assert APICallLog.objects.filter(response_details__message='وضعیت حیات کاربر مورد تائید نیست').count() == 1

        mock.post.return_value = self.mock_liveness('no_verification_field')
        assert self.auto_kyc_instance.check_user_liveness(self.req) == self.EXPECTED_RESPONSE['no_verification_field']
        assert APICallLog.objects.filter(response_details__message='خطایی رخ داده است').count() == 4
        assert APICallLog.objects.filter(response_details__message='هویت کاربر مورد تائید نیست').count() == 1
        assert APICallLog.objects.filter(response_details__message='وضعیت حیات کاربر مورد تائید نیست').count() == 1

        mock.post.return_value = self.mock_liveness('no_liveness_field')
        assert self.auto_kyc_instance.check_user_liveness(self.req) == self.EXPECTED_RESPONSE['no_liveness_field']
        assert APICallLog.objects.filter(response_details__message='خطایی رخ داده است').count() == 5
        assert APICallLog.objects.filter(response_details__message='هویت کاربر مورد تائید نیست').count() == 1
        assert APICallLog.objects.filter(response_details__message='وضعیت حیات کاربر مورد تائید نیست').count() == 1

    @patch('requests.post')
    def test_check_user_liveness_old_format(self, mock):
        mock.return_value = OldLivenessMockResponse()
        expected_result = {
            'result': True,
            'message': 'ok',
            'confidence': 100,
            'apiresponse': {
                'liveness': {'verification_result': True, 'liveness_result': True}
            }
        }
        assert expected_result == self.auto_kyc_instance.check_user_liveness(self.req)

        mock.return_value = OldLivenessMockResponse('not_verification')
        expected_result = {
            'result': False,
            'message': 'هویت کاربر مورد تائید نیست',
            'confidence': 50,
            'apiresponse': {
                'liveness': {'verification_result': False, 'liveness_result': True}
            }
        }
        assert expected_result == self.auto_kyc_instance.check_user_liveness(self.req)

        mock.return_value = OldLivenessMockResponse('not_liveness')
        expected_result = {
            'result': False,
            'message': 'وضعیت حیات کاربر مورد تائید نیست',
            'confidence': 50,
            'apiresponse': {
                'liveness': {'verification_result': True, 'liveness_result': False}
            }
        }
        assert expected_result == self.auto_kyc_instance.check_user_liveness(self.req)
        assert APICallLog.objects.count() == 3
        assert APICallLog.objects.filter(response_details__message='ok').count() == 1
        assert APICallLog.objects.filter(response_details__message='هویت کاربر مورد تائید نیست').count() == 1
        assert APICallLog.objects.filter(response_details__message='وضعیت حیات کاربر مورد تائید نیست').count() == 1

    @patch('exchange.integrations.auto_kyc_rest_wrapper.requests')
    def test_check_user_verification_when_user_is_trader(self, mock):
        self.assertEqual(self.user.user_type, User.USER_TYPES.level1)
        mock.post.return_value = self.mock_liveness('success')
        assert self.auto_kyc_instance.check_user_liveness(self.req) == self.EXPECTED_RESPONSE['success']
        self.assertEqual(self.user.user_type, User.USER_TYPES.level2)

        self.user.user_type = User.USER_TYPES.trader
        self.user.save(update_fields=['user_type'])

        # success process
        self.assertEqual(self.user.user_type, User.USER_TYPES.trader)
        mock.post.return_value = self.mock_liveness('success')
        assert self.auto_kyc_instance.check_user_liveness(self.req) == self.EXPECTED_RESPONSE['success']
        self.assertEqual(self.user.user_type, User.USER_TYPES.trader)

        # fail process
        self.assertEqual(self.user.user_type, User.USER_TYPES.trader)
        mock.post.return_value = self.mock_liveness('status_400')
        assert self.auto_kyc_instance.check_user_liveness(self.req) == self.EXPECTED_RESPONSE['status_400']
        self.assertEqual(self.user.user_type, User.USER_TYPES.trader)
        assert APICallLog.objects.count() == 3
        assert APICallLog.objects.filter(response_details__message='ok').count() == 2
        assert APICallLog.objects.filter(response_details__message='خطایی رخ داده است').count() == 1

    @patch('exchange.integrations.auto_kyc_rest_wrapper.requests')
    def test_failed_calling_api(self, mock):
        mock.post.return_value = self.mock_liveness(tp='success')
        result = self.auto_kyc_instance.check_user_liveness(self.req)
        assert not self.auto_kyc_instance.failed_calling_api(result)

        mock.post.return_value = self.mock_liveness(tp='not_verification')
        result = self.auto_kyc_instance.check_user_liveness(self.req)
        assert not self.auto_kyc_instance.failed_calling_api(result)

        mock.post.return_value = self.mock_liveness(tp='not_liveness')
        result = self.auto_kyc_instance.check_user_liveness(self.req)
        assert not self.auto_kyc_instance.failed_calling_api(result)

        mock.post.return_value = self.mock_liveness(tp='status_400')
        result = self.auto_kyc_instance.check_user_liveness(self.req)
        assert self.auto_kyc_instance.failed_calling_api(result)

        mock.post.return_value = self.mock_liveness(tp='status_200_but_error')
        result = self.auto_kyc_instance.check_user_liveness(self.req)
        assert self.auto_kyc_instance.failed_calling_api(result)

        mock.post.return_value = self.mock_liveness(tp='status_200_but_liveness_error')
        result = self.auto_kyc_instance.check_user_liveness(self.req)
        assert self.auto_kyc_instance.failed_calling_api(result)

        mock.post.return_value = self.mock_liveness(tp='no_verification_field')
        result = self.auto_kyc_instance.check_user_liveness(self.req)
        assert self.auto_kyc_instance.failed_calling_api(result)

        mock.post.return_value = self.mock_liveness(tp='no_liveness_field')
        result = self.auto_kyc_instance.check_user_liveness(self.req)
        assert self.auto_kyc_instance.failed_calling_api(result)

    @patch('exchange.integrations.auto_kyc_rest_wrapper.requests')
    def test_calling_with_birthdate_or_serial(self, mock):
        mock.post.return_value = self.mock_liveness('success')
        url = 'https://napi.jibit.ir/newalpha/api/authorization'
        headers = {'Accept': 'application/json', 'Authorization': 'Bearer 2|oz2RgIEktKwzaQYgLwVGXkWV6UhtmD4jT99fJjYF'}
        timeout = 30
        assert self.auto_kyc_instance.check_user_liveness(self.req) == self.EXPECTED_RESPONSE['success']
        mock.post.assert_called_once_with(
            url,
            headers=headers,
            data={'ssn': None, 'serial': None, 'birth_date': None, 'liveness_threshold': 0.9},
            files=ANY,
            timeout=timeout,
        )

        mock.reset_mock()
        self.user.national_code = '12312345678'
        self.user.national_serial_number = '1A2B3C4D'
        self.user.save(update_fields=('national_code', 'national_serial_number'))
        assert self.auto_kyc_instance.check_user_liveness(self.req) == self.EXPECTED_RESPONSE['success']
        mock.post.assert_called_once_with(
            url,
            headers=headers,
            data={'ssn': '12312345678', 'serial': '1A2B3C4D', 'birth_date': None, 'liveness_threshold': 0.9},
            files=ANY,
            timeout=timeout,
        )

        mock.reset_mock()
        self.user.birthday = datetime.date(year=2024, month=9, day=8)
        self.user.save(update_fields=('birthday',))
        assert self.auto_kyc_instance.check_user_liveness(self.req) == self.EXPECTED_RESPONSE['success']
        mock.post.assert_called_once_with(
            url,
            headers=headers,
            data={'ssn': '12312345678', 'serial': '1A2B3C4D', 'birth_date': '1403/06/18', 'liveness_threshold': 0.9},
            files=ANY,
            timeout=timeout,
        )

        mock.reset_mock()
        self.user.national_serial_number = None
        self.user.save(update_fields=('national_serial_number',))
        assert self.auto_kyc_instance.check_user_liveness(self.req) == self.EXPECTED_RESPONSE['success']
        mock.post.assert_called_once_with(
            url,
            headers=headers,
            data={'ssn': '12312345678', 'serial': None, 'birth_date': '1403/06/18', 'liveness_threshold': 0.9},
            files=ANY,
            timeout=timeout,
        )
