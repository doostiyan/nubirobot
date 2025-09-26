from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from exchange.accounts.models import User, UserSms
from exchange.accounts.sms_config import AGGREGATED_LOAD_BALANCER, SMS_PROVIDER_LOAD_BALANCER_CONFIG_key, SmsProvider
from exchange.accounts.sms_integrations import SmsSender
from exchange.accounts.sms_templates import OLD_TEMPLATE_NUMBER_TO_TEMPLATE_NAME_DICT
from exchange.base.models import Settings


class SmsProviderLoadBalancerTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user.mobile = '09131234567'
        self.user.save(update_fields=('mobile',))
        self.default_template = 0  # 'default'
        self.sms_template = 77788  # 'user_merge_otp'
        self.sms = UserSms.objects.create(
            user=self.user,
            to=self.user.mobile,
            tp=UserSms.TYPES.manual,
            text='123',
            template=UserSms.TEMPLATES.user_merge_otp,
        )
        Settings.set_cached_json(SMS_PROVIDER_LOAD_BALANCER_CONFIG_key, AGGREGATED_LOAD_BALANCER)

    def test_sms_with_no_template_sent_from_old_smsir_provider(self):
        assert SmsSender.load_balance_between_providers(self.default_template) == SmsProvider.OLD_SMSIR.value

    @patch('exchange.accounts.sms_integrations.random.random', new_callable=MagicMock)
    def test_sms_with_template_sent_from_different_providers(self, mock_random):
        mock_random.return_value = 0  # Kavenegar's change is zero for now and it should not send messages
        assert SmsSender.load_balance_between_providers(self.sms_template) == SmsProvider.NEW_SMSIR.value

        mock_random.return_value = 0.5
        assert SmsSender.load_balance_between_providers(self.sms_template) == SmsProvider.NEW_SMSIR.value

        mock_random.return_value = 0.6
        assert SmsSender.load_balance_between_providers(self.sms_template) == SmsProvider.FINNOTEXT.value

        mock_random.return_value = 0.9
        assert SmsSender.load_balance_between_providers(self.sms_template) == SmsProvider.OLD_SMSIR.value

    @patch('exchange.accounts.sms_integrations.random.random', new_callable=MagicMock)
    def test_sms_with_template_sent_from_different_providers_with_changed_settings(self, mock_random):
        changed_settings = {
            SmsProvider.KAVENEGAR.value: 0.1,
            SmsProvider.NEW_SMSIR.value: 0.2,
            SmsProvider.FINNOTEXT.value: 0.8,
            SmsProvider.OLD_SMSIR.value: 1,
        }
        load_balance_config = Settings.get_cached_json(
            SMS_PROVIDER_LOAD_BALANCER_CONFIG_key, default=AGGREGATED_LOAD_BALANCER
        )
        load_balance_config[OLD_TEMPLATE_NUMBER_TO_TEMPLATE_NAME_DICT[self.sms_template]] = changed_settings
        Settings.set_cached_json(SMS_PROVIDER_LOAD_BALANCER_CONFIG_key, load_balance_config)

        mock_random.return_value = 0.01
        assert SmsSender.load_balance_between_providers(self.sms_template) == SmsProvider.KAVENEGAR.value

        mock_random.return_value = 0.1
        assert SmsSender.load_balance_between_providers(self.sms_template) == SmsProvider.NEW_SMSIR.value

        mock_random.return_value = 0.2
        assert SmsSender.load_balance_between_providers(self.sms_template) == SmsProvider.FINNOTEXT.value

        mock_random.return_value = 0.8
        assert SmsSender.load_balance_between_providers(self.sms_template) == SmsProvider.OLD_SMSIR.value

    @override_settings(IS_PROD=True)
    @patch('exchange.accounts.sms_integrations.KavenegarClient.send', new_callable=MagicMock)
    @patch('exchange.accounts.sms_integrations.NewSmsIrClient.send', new_callable=MagicMock)
    @patch('exchange.accounts.sms_integrations.SmsSender.send_with_finnotext', new_callable=MagicMock)
    @patch('exchange.accounts.sms_integrations.OldSmsIrClient.send', new_callable=MagicMock)
    @patch('exchange.accounts.sms_integrations.random.random', new_callable=MagicMock)
    def test_send_sms_from_correct_provider(
        self,
        mock_random,
        mock_old_sms_ir_send,
        mock_finnotext_send,
        mock_new_sms_ir_send,
        mock_kavenegar_send,
    ):
        changed_settings = {
            SmsProvider.KAVENEGAR.value: 0.1,
            SmsProvider.NEW_SMSIR.value: 0.2,
            SmsProvider.FINNOTEXT.value: 0.8,
            SmsProvider.OLD_SMSIR.value: 1,
        }
        load_balance_config = Settings.get_cached_json(
            SMS_PROVIDER_LOAD_BALANCER_CONFIG_key, default=AGGREGATED_LOAD_BALANCER
        )
        load_balance_config[OLD_TEMPLATE_NUMBER_TO_TEMPLATE_NAME_DICT[self.sms_template]] = changed_settings
        Settings.set_cached_json(SMS_PROVIDER_LOAD_BALANCER_CONFIG_key, load_balance_config)

        mock_random.return_value = 0.01
        SmsSender.send(self.sms)
        mock_old_sms_ir_send.assert_not_called()
        mock_finnotext_send.assert_not_called()
        mock_new_sms_ir_send.assert_not_called()
        mock_kavenegar_send.assert_called_once_with(self.sms)

        mock_old_sms_ir_send.reset_mock()
        mock_finnotext_send.reset_mock()
        mock_new_sms_ir_send.reset_mock()
        mock_kavenegar_send.reset_mock()
        mock_random.return_value = 0.1
        SmsSender.send(self.sms)
        mock_old_sms_ir_send.assert_not_called()
        mock_finnotext_send.assert_not_called()
        mock_new_sms_ir_send.assert_called_once_with(self.sms)
        mock_kavenegar_send.assert_not_called()

        mock_old_sms_ir_send.reset_mock()
        mock_finnotext_send.reset_mock()
        mock_new_sms_ir_send.reset_mock()
        mock_kavenegar_send.reset_mock()
        mock_random.return_value = 0.2
        SmsSender.send(self.sms)
        mock_old_sms_ir_send.assert_not_called()
        mock_finnotext_send.assert_called_once_with(self.sms)
        mock_new_sms_ir_send.assert_not_called()
        mock_kavenegar_send.assert_not_called()

        mock_old_sms_ir_send.reset_mock()
        mock_finnotext_send.reset_mock()
        mock_new_sms_ir_send.reset_mock()
        mock_kavenegar_send.reset_mock()
        mock_random.return_value = 0.8
        SmsSender.send(self.sms)
        mock_old_sms_ir_send.assert_called_once_with(self.sms)
        mock_finnotext_send.assert_not_called()
        mock_new_sms_ir_send.assert_not_called()
        mock_kavenegar_send.assert_not_called()
