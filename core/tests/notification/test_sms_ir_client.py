from unittest import mock
from unittest.mock import patch
from uuid import UUID

import responses
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings

from exchange.accounts.models import User, UserSms
from exchange.accounts.sms_integrations import SmsSender
from exchange.notification.constants import SMS_IR_BASE_URL, SMS_IR_SETTINGS_TOKEN_KEY
from exchange.notification.models import Sms
from exchange.notification.sms.sms_integrations import OldSmsIrClient
from tests.notification.helpers import Request


class SMSIrClientTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test-user1', mobile='09151234567')
        self.sample_text_message = 'sample_text_message'
        self.simple_send_url = 'http://restfulsms.com/api/MessageSend'
        self.fast_send_url = 'http://restfulsms.com/api/UltraFastSend'

    @patch('exchange.notification.sms.sms_integrations.requests.post')
    def test_send_sms_ok(self, requests_mock):
        requests_mock.return_value = Request(
            output={
                'IsSuccessful': True,
                'Message': 'ok',
                'BatchKey': '123',
                'TokenKey': 123,
                'ids': [{'id': '1000'}, {'id': '2000'}],
            }
        )

        expected_data = {
            'Messages': [self.sample_text_message + '\n' + 'لغو 11'],
            'MobileNumbers': [self.user.mobile],
            'LineNumber': '100091070325',
            'SendDateTime': '',
            'CanContinueInCaseOfError': 'false',
        }

        sms_client = OldSmsIrClient()
        sms = Sms.objects.create(
            user_id=self.user.id,
            to=self.user.mobile,
            tp=Sms.TYPES.user_merge,
            text=self.sample_text_message,
            template=0,
        )
        sms_client.send(sms)
        assert Sms.objects.filter(delivery_status='Sent: 123', details='Sent: 123').exists()
        requests_mock.assert_called_with(
            self.simple_send_url, json=expected_data, headers={'x-sms-ir-secure-token': 123}, timeout=8
        )

    @patch('exchange.notification.sms.sms_integrations.requests.post')
    def test_send_sms_nok(self, requests_mock):
        requests_mock.return_value = Request(
            output={
                'IsSuccessful': False,
                'Message': 'The message was not successful cuz of my bad mood!',
                'BatchKey': '123',
                'TokenKey': 123,
                'ids': [{'id': '1000'}, {'id': '2000'}],
            }
        )
        expected_data = {
            'Messages': [self.sample_text_message + '\n' + 'لغو 11'],
            'MobileNumbers': [self.user.mobile],
            'LineNumber': '100091070325',
            'SendDateTime': '',
            'CanContinueInCaseOfError': 'false',
        }

        sms_client = OldSmsIrClient()
        sms = Sms.objects.create(
            user_id=self.user.id,
            to=self.user.mobile,
            tp=Sms.TYPES.user_merge,
            text=self.sample_text_message,
            template=0,
        )
        sms_client.send(sms)
        assert Sms.objects.filter(
            delivery_status='Sent: Unsuccessful', details='Failed:The message was not successful cuz of my bad mood!'
        ).exists()
        requests_mock.assert_called_with(
            self.simple_send_url, json=expected_data, headers={'x-sms-ir-secure-token': 123}, timeout=8
        )

    @patch('exchange.notification.sms.sms_integrations.requests.post')
    def test_send_fast_sms_ok(self, requests_mock):
        requests_mock.return_value = Request(
            output={
                'IsSuccessful': True,
                'Message': 'The message was successful',
                'VerificationCodeId': '123',
                'TokenKey': 123,
                'ids': [{'id': '1000'}, {'id': '2000'}],
            }
        )

        sms_client = OldSmsIrClient()
        sms = Sms.objects.create(
            user_id=self.user.id, to=self.user.mobile, tp=Sms.TYPES.verify_phone, text='124', template=3065
        )
        sms_client.send(sms)
        assert Sms.objects.filter(delivery_status='Sent: 123', details='Sent: 123').exists()
        requests_mock.assert_called_with(
            self.fast_send_url,
            json={
                'ParameterArray': [{'Parameter': 'VerificationCode', 'ParameterValue': '124'}],
                'Mobile': '09151234567',
                'TemplateId': '3065',
            },
            headers={'x-sms-ir-secure-token': 123},
            timeout=8,
        )

    @patch('exchange.notification.sms.sms_integrations.requests.post')
    def test_send_fast_sms_nok(self, requests_mock):
        requests_mock.return_value = Request(
            output={
                'IsSuccessful': False,
                'Message': 'The message was not successful cuz of my bad mood!',
                'VerificationCodeId': '123',
                'TokenKey': 123,
                'ids': [{'id': '1000'}, {'id': '2000'}],
            }
        )

        sms_client = OldSmsIrClient()
        sms = Sms.objects.create(
            user_id=self.user.id, to=self.user.mobile, tp=Sms.TYPES.verify_phone, text='124', template=3065
        )
        sms_client.send(sms)
        assert Sms.objects.filter(
            delivery_status='Sent: Unsuccessful', details='Failed:The message was not successful cuz of my bad mood!'
        ).exists()
        requests_mock.assert_called_with(
            self.fast_send_url,
            json={
                'ParameterArray': [{'Parameter': 'VerificationCode', 'ParameterValue': '124'}],
                'Mobile': '09151234567',
                'TemplateId': '3065',
            },
            headers={'x-sms-ir-secure-token': 123},
            timeout=8,
        )

    @responses.activate
    def test_send_sms_token_renew_token_failed(self):
        cache.delete(SMS_IR_SETTINGS_TOKEN_KEY)
        responses.post(
            url=f'{SMS_IR_BASE_URL}/Token',
            json={
                'Message': 'test_error_message',
            },
            status=200,
        )
        sms_client = OldSmsIrClient()
        sms = Sms.objects.create(
            user_id=self.user.id,
            to=self.user.mobile,
            tp=Sms.TYPES.verify_phone,
            text='value1\nvalue2\nvalue3',
            template=1,
        )
        sms_client.send(sms)
        assert Sms.objects.filter(id=sms.id, details='Cannot get token:test_error_message').exists()

    @responses.activate
    def test_send_sms_token_renew_token_success(self):
        responses.post(
            url=f'{SMS_IR_BASE_URL}/Token',
            json={
                'TokenKey': 'test_token_sms_ir',
            },
            status=200,
        )
        responses.post(
            url=f'{SMS_IR_BASE_URL}/UltraFastSend',
            json={
                'IsSuccessful': 'true',
                'Message': 'Message sent successfully',
                'VerificationCodeId': '100',
                'ids': [
                    {'id': '1'},
                    {'id': '2'},
                ],
            },
            status=200,
        )

        sms_client = OldSmsIrClient()
        sms = Sms.objects.create(
            user_id=self.user.id,
            to=self.user.mobile,
            tp=Sms.TYPES.verify_phone,
            text='value1\nvalue2\nvalue3',
            template=3065,
        )
        sms_client.send(sms)
        assert Sms.objects.filter(id=sms.id, delivery_status='Sent: 100', details='Sent: 100').exists()


class FinnotechOTPClientTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test-user1', mobile='09151234567')

    @responses.activate
    @override_settings(IS_PROD=True)
    @mock.patch('exchange.accounts.sms_integrations.uuid4', return_value=UUID('f63b6ac4-fd88-4373-b9be-e8626e8ef939'))
    def test_send_sms_finnotext_otp_ok(self, mocked_uuid):
        cache.set(SMS_IR_SETTINGS_TOKEN_KEY, 'test_token')
        responses.post(
            url=f'https://apibeta.finnotech.ir/facility/v2/clients/{settings.MARKETING_FINNOTEXT_CLIENT_ID}/finnotextOtp',
            json={
                "trackId": "43d70b50-c767-4ef6-b220-202610782b05",
                "result": {"message": "درخواست شما با موفقیت دریافت شد"},
                "status": "DONE",
            },
            status=200,
        )

        user_sms = UserSms.objects.create(
            user=self.user,
            tp=UserSms.TYPES.verify_withdraw,
            to=self.user.mobile,
            text='test',
            template=UserSms.TEMPLATES.withdraw,
        )
        SmsSender().send_with_finnotext(user_sms)
        user_sms.refresh_from_db()
        assert user_sms.details == "Sent: {'message': 'درخواست شما با موفقیت دریافت شد'}"
        assert user_sms.delivery_status == 'Sent: f63b6ac4-fd88-4373-b9be-e8626e8ef939'
        assert user_sms.carrier == 1

    @responses.activate
    @override_settings(IS_PROD=True)
    @mock.patch('exchange.accounts.sms_integrations.uuid4', return_value=UUID('f63b6ac4-fd88-4373-b9be-e8626e8ef939'))
    def test_send_sms_finnotext_otp_error(self, mocked_uuid):
        cache.set(SMS_IR_SETTINGS_TOKEN_KEY, 'test_token')
        responses.post(
            url=f'https://apibeta.finnotech.ir/facility/v2/clients/{settings.MARKETING_FINNOTEXT_CLIENT_ID}/finnotextOtp',
            json={
                "trackId": "abbd6700-6e45-43fe-8cd5-aaaaa90ac",
                "status": "FAILED",
                "error": {"code": "VALIDATION_ERROR", "message": "سرشماره برای کلاینت ثبت نشده است"},
            },
            status=400,
        )

        user_sms = UserSms.objects.create(
            user=self.user,
            tp=UserSms.TYPES.verify_withdraw,
            to=self.user.mobile,
            text='test',
            template=UserSms.TEMPLATES.withdraw,
        )
        SmsSender().send_with_finnotext(user_sms)
        user_sms.refresh_from_db()
        assert user_sms.details == "Failed: {'code': 'VALIDATION_ERROR', 'message': 'سرشماره برای کلاینت ثبت نشده است'}"
        assert user_sms.delivery_status == 'Sent: Unsuccessful'
        assert user_sms.carrier == 1

    def test_sms_full_text(self):
        user_sms = UserSms.objects.create(
            user=self.user,
            tp=UserSms.TYPES.verify_withdraw,
            to=self.user.mobile,
            text='test',
            template=UserSms.TEMPLATES.withdraw,
        )
        assert user_sms.sms_full_text == 'هشدار!\nاین کد تایید «برداشت» از حساب نوبیتکس شماست: test'

        user_sms = UserSms.objects.create(
            user=self.user,
            tp=UserSms.TYPES.user_merge,
            to=self.user.mobile,
            text='test\n091312345678',
            template=UserSms.TEMPLATES.user_merge_otp,
        )
        assert user_sms.sms_full_text == (
            'هشدار نوبیتکس!\nکد امنیتی برای تایید ادغام شماره تماس شما با حساب زیر:'
            '\ntest\nکد تایید ادغام:\n091312345678'
        )
