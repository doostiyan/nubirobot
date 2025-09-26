from unittest.mock import patch

import responses
from django.conf import settings
from django.test import TestCase, override_settings

from exchange.accounts.models import User, UserSms
from exchange.accounts.sms_integrations import KavenegarClient


class KavenegarClientTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user.mobile = '09131234567'
        self.user.save(update_fields=('mobile',))
        self.one_token_at_the_end_sms = UserSms.objects.create(
            user=self.user,
            to=self.user.mobile,
            tp=UserSms.TYPES.manual,
            text='123',
            template=UserSms.TEMPLATES.tfa_enable,
        )
        self.one_token_in_the_middle_sms = UserSms.objects.create(
            user=self.user,
            to=self.user.mobile,
            tp=UserSms.TYPES.manual,
            text='456',
            template=UserSms.TEMPLATES.verification,
        )
        self.multiple_token_in_the_middle_sms = UserSms.objects.create(
            user=self.user,
            to=self.user.mobile,
            tp=UserSms.TYPES.manual,
            text='123\n456\n789',
            template=UserSms.TEMPLATES.abc_liquidate_by_provider,
        )
        self.multiple_token_at_the_end_sms = UserSms.objects.create(
            user=self.user,
            to=self.user.mobile,
            tp=UserSms.TYPES.manual,
            text='123\n456',
            template=UserSms.TEMPLATES.user_merge_otp,
        )

    def test_extracting_parameter_map_from_template(self):
        params = KavenegarClient._get_parameters_map(self.one_token_at_the_end_sms)
        assert params == {'token': '123'}

        params = KavenegarClient._get_parameters_map(self.one_token_in_the_middle_sms)
        assert params == {'token': '456'}

        params = KavenegarClient._get_parameters_map(self.multiple_token_in_the_middle_sms)
        assert params == {'token': '123', 'token2': '456', 'token3': '789'}

        params = KavenegarClient._get_parameters_map(self.multiple_token_at_the_end_sms)
        assert params == {'token': '123', 'token2': '456'}

    @responses.activate
    @override_settings(IS_PROD=True)
    def test_send_sms_with_kavenegar_ok(self):
        responses.post(
            url=f'https://api.kavenegar.com/v1/{settings.KAVENEGAR_SMS_API_KEY}/verify/lookup.json'
            '?receptor=09131234567'
            '&token=123'
            '&token2=456'
            '&token3=789'
            '&template=AbcLiquidateByProvider',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded',
                'charset': 'utf-8',
            },
            json={
                'return': {'status': 200, 'message': 'تایید شد'},
                'entries': [
                    {
                        'messageid': 8792343,
                        'message': 'مقدار 123 تومان از وثیقه‌ی 456 به‌درخواست 789 تبدیل و تسویه شد.',
                        'status': 5,
                        'statustext': 'ارسال به مخابرات',
                        'sender': '10004346',
                        'receptor': '09131234567',
                        'date': 1356619709,
                        'cost': 120,
                    }
                ],
            },
            status=200,
        )

        KavenegarClient.send(self.multiple_token_in_the_middle_sms)
        self.multiple_token_in_the_middle_sms.refresh_from_db()
        assert self.multiple_token_in_the_middle_sms.details == 'Sent: ارسال به مخابرات'
        assert self.multiple_token_in_the_middle_sms.provider_id == 8792343
        assert self.multiple_token_in_the_middle_sms.delivery_status == 'Sent: ارسال به مخابرات'
        assert self.multiple_token_in_the_middle_sms.carrier == 3

    @responses.activate
    @override_settings(IS_PROD=True)
    def test_send_sms_with_kavenegar_nok(self):
        responses.post(
            url=f'https://api.kavenegar.com/v1/{settings.KAVENEGAR_SMS_API_KEY}/verify/lookup.json'
            '?receptor=09131234567'
            '&token=123'
            '&template=TfaEnable',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded',
                'charset': 'utf-8',
            },
            json={'return': {'status': 418, 'message': 'اعتبار حساب شما کافی نیست'}},
            status=200,
        )

        KavenegarClient.send(self.one_token_at_the_end_sms)
        self.one_token_at_the_end_sms.refresh_from_db()
        assert self.one_token_at_the_end_sms.details == 'Failed: اعتبار حساب شما کافی نیست'
        assert self.one_token_at_the_end_sms.provider_id is None
        assert self.one_token_at_the_end_sms.delivery_status == 'Sent: Unsuccessful'
        assert self.one_token_at_the_end_sms.carrier == 3
