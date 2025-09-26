from unittest.mock import call, patch
from uuid import uuid4

from django.core.cache import cache
from django.test import TestCase, override_settings

from exchange.accounts.models import User, UserSms
from exchange.base.models import Settings
from exchange.broker.broker.schema import SMSSchema
from exchange.notification.consumers import fast_sms_callback, sms_callback
from exchange.notification.models import InAppNotification, Sms
from exchange.notification.sms.sms_config import SmsProvider
from tests.base.utils import mock_on_commit
from tests.notification.helpers import Request

UID_1 = uuid4()
UID_2 = uuid4()
MOBILE_1 = '09151234567'
MOBILE_2 = '09121234567'
MOCK_SMS_LIST = [
    SMSSchema(user_id=str(UID_1), text='msg1', to=MOBILE_1, tp=1, template=3065),
    SMSSchema(user_id=str(UID_1), text='msg2', to=MOBILE_1, tp=2, template=72801),
    SMSSchema(user_id=str(UID_2), text='msg3', to=MOBILE_2, tp=3, template=0),
    SMSSchema(user_id=str(uuid4()), text='invalid-uid', to=MOBILE_1, tp=1, template=3065),
]


@override_settings(IS_PROD=True)
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
@patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
class ConsumerSMSTest(TestCase):
    def setUp(self):
        cache.set('settings_is_sms_broker_enabled', 'true')
        cache.set('settings_kafka_broker_enabled', 'true')
        self.user1 = User.objects.create_user(username='test-user1', uid=UID_1)
        self.user2 = User.objects.create_user(username='test-user2', uid=UID_2)

    @patch('exchange.notification.sms.sms_integrations.SmsSender.send')
    def test_consume_sms_topic(self, sms_handler_mock, _):
        Settings.set('send_sms', 'yes')
        for input_sms in MOCK_SMS_LIST:
            sms_callback(input_sms, ack=lambda: None)

        # Database assertions
        assert Sms.objects.filter(user__uid=UID_1).count() == 2
        assert Sms.objects.filter(user__uid=UID_2).count() == 1
        assert Sms.objects.filter(user__isnull=True).count() == 1
        assert Sms.objects.count() == 4

        # Check if send and set_method were called 4 times each
        assert (
            sms_handler_mock.call_count == 4
        ), f'Expected 4 calls to send, but got {sms_handler_mock.send.call_count}.'

    @patch('exchange.notification.sms.sms_integrations.SmsSender.send')
    def test_consume_sms_with_new_logic(self, simple_sms_mock, _):
        Settings.set('send_sms', 'yes')
        for input_sms in MOCK_SMS_LIST:
            sms_callback(input_sms, ack=lambda: None)
        sms_list = list(map(call, Sms.objects.all()))
        simple_sms_mock.assert_has_calls(sms_list, any_order=True)

    @patch('exchange.notification.sms.sms_integrations.requests.post', return_value=Request())
    @patch(
        'exchange.notification.sms.sms_integrations.SmsSender.load_balance_between_providers',
        return_value=SmsProvider.OLD_SMSIR.value,
    )
    def test_consume_sms_with_new_logic_mock_integration(self, load_balancer_mock, send_message_mock, _):

        Settings.set('send_sms', 'yes')
        for input_sms in MOCK_SMS_LIST:
            sms_callback(input_sms, ack=lambda: None)

        assert Sms.objects.filter(delivery_status='Sent: 12456', details='Sent: 12456').count() == 3
        assert Sms.objects.filter(delivery_status='Sent: 1235', details='Sent: 1235').count() == 1

    @patch('exchange.notification.sms.sms_integrations.requests.post', return_value=Request())
    @patch(
        'exchange.notification.sms.sms_integrations.SmsSender.load_balance_between_providers',
        return_value=SmsProvider.OLD_SMSIR.value,
    )
    def test_consume_fast_sms_with_new_logic_mock_integration(self, load_balancer_mock, send_message_mock, _):
        Settings.set('send_sms', 'yes')
        for input_sms in MOCK_SMS_LIST:
            fast_sms_callback(input_sms, ack=lambda: None)
        assert Sms.objects.filter(delivery_status='Sent: 12456', details='Sent: 12456').count() == 3
        assert Sms.objects.filter(delivery_status='Sent: 1235', details='Sent: 1235').count() == 1

    @patch('exchange.notification.sms.sms_integrations.requests.post', return_value=Request())
    @patch(
        'exchange.notification.sms.sms_integrations.SmsSender.load_balance_between_providers',
        return_value=SmsProvider.OLD_SMSIR.value,
    )
    def test_consume_fast_sms_multiple_number_sending_failed(self, load_balancer_mock, send_message_mock, _):
        Settings.set('send_sms', 'yes')
        input_smses = [
            SMSSchema(user_id=str(UID_1), text='msg1', to=f'{MOBILE_1},{MOBILE_2}', tp=1, template=3065),
            *MOCK_SMS_LIST,
        ]
        for input_sms in input_smses:
            fast_sms_callback(input_sms, ack=lambda: None)

        assert (
            Sms.objects.filter(delivery_status='Sent: 12456', details='Sent: 12456').count() == 4
        )  # not 6. the command has handled just first number of the "to" field
        assert Sms.objects.filter(delivery_status='Sent: 1235', details='Sent: 1235').count() == 1

    @override_settings(IS_PROD=False)
    @patch('exchange.notification.sms.sms_integrations.SmsSender.send')
    def test_consume_emulated_sms_with_new_logic_mock_integration(self, send_message_mock, _):
        send_message_mock.return_value = (
            True,
            {
                'delivery_status': 'delivered',
                'details': 'the sms is delivered to the user',
            },
        )
        Settings.set('send_sms', 'yes')
        for input_sms in MOCK_SMS_LIST:
            sms_callback(input_sms, ack=lambda: None)

        assert Sms.objects.filter(delivery_status='Sent: faked', details='Sent: faked').count() == 4
        assert InAppNotification.objects.all().count() == 3

        assert (
            InAppNotification.objects.filter(
                user=self.user1,
                message='شبیه‌سازی ارسال پیامک: کد تایید شما در سایت نوبیتکس msg1 است ',
            ).count()
            == 1
        )

        assert (
            InAppNotification.objects.filter(
                user=self.user1,
                message='شبیه‌سازی ارسال پیامک: هشدار!\nاین کد تایید «برداشت» از حساب نوبیتکس شماست: msg2',
            ).count()
            == 1
        )

        assert (
            InAppNotification.objects.filter(
                user=self.user2,
                message='شبیه‌سازی ارسال پیامک: msg3',
            ).count()
            == 1
        )

    def test_consume_sms_topic_without_user(self, _):
        intput_sms = SMSSchema(user_id=None, text='12345', to=MOBILE_1, tp=1, template=2)
        fast_sms_callback(intput_sms, ack=lambda: None)

        assert Sms.objects.filter(user__isnull=True).count() == 1
        assert Sms.objects.count() == 1


@override_settings(IS_PROD=True)
class SMSFlagTests(TestCase):
    def setUp(self):
        Settings.set('send_sms', 'yes')
        cache.set('settings_kafka_broker_enabled', 'true')
        self.user = User.objects.create_user(username='test-user', mobile='09151234567', uid=UID_1)

    @patch('exchange.accounts.signals.produce_sms_event')
    def test_flag_sms_produce(self, produce_event_mock):
        with patch('exchange.accounts.signals.NotificationConfig.is_sms_logging_enabled') as mock_sms_log:
            mock_sms_log.return_value = False
            UserSms.objects.create(
                user=self.user,
                tp=UserSms.TYPES.verify_withdraw,
                to=self.user.mobile,
                text='test',
                template=UserSms.TEMPLATES.withdraw,
            )
            produce_event_mock.assert_not_called()

        with patch('exchange.accounts.signals.NotificationConfig.is_sms_logging_enabled') as mock_sms_log:
            mock_sms_log.return_value = True
            UserSms.objects.create(
                user=self.user,
                tp=UserSms.TYPES.verify_withdraw,
                to=self.user.mobile,
                text='test',
                template=UserSms.TEMPLATES.withdraw,
            )
            produce_event_mock.assert_called_once()

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.accounts.signals.task_send_user_sms.apply_async')
    def test_check_sms_broker_flag(self, task_send_sms_mock, _):
        with patch('exchange.accounts.signals.NotificationConfig.is_sms_broker_enabled') as mock_sms_broker:
            mock_sms_broker.return_value = False
            UserSms.objects.create(
                user=self.user,
                tp=UserSms.TYPES.verify_withdraw,
                to=self.user.mobile,
                text='test',
                template=UserSms.TEMPLATES.withdraw,
            )
            task_send_sms_mock.assert_called_once()

        task_send_sms_mock.reset_mock()
        with patch('exchange.accounts.signals.NotificationConfig.is_sms_broker_enabled') as mock_sms_broker:
            mock_sms_broker.return_value = True
            UserSms.objects.create(
                user=self.user,
                tp=UserSms.TYPES.verify_withdraw,
                to=self.user.mobile,
                text='test',
                template=UserSms.TEMPLATES.withdraw,
            )
            task_send_sms_mock.assert_not_called()

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.notification.management.commands.consume_topic_sms.task_send_sms.delay')
    def test_consume_sms_broker_flag(self, task_send_sms_mock, _):
        with patch(
            'exchange.notification.management.commands.consume_topic_sms.NotificationConfig.is_sms_broker_enabled'
        ) as mock_sms_broker:
            mock_sms_broker.return_value = False
            for input_sms in MOCK_SMS_LIST:
                sms_callback(input_sms, ack=lambda: None)
            task_send_sms_mock.assert_not_called()

        task_send_sms_mock.reset_mock()
        Sms.objects.all().delete()
        with patch(
            'exchange.notification.management.commands.consume_topic_sms.NotificationConfig.is_sms_broker_enabled'
        ) as mock_sms_broker:
            mock_sms_broker.return_value = True
            for input_sms in MOCK_SMS_LIST:
                sms_callback(input_sms, ack=lambda: None)
            sms_list = [call(sms_id=sms.id, is_fast=False) for sms in Sms.objects.all()]
            task_send_sms_mock.assert_has_calls(sms_list, any_order=True)
