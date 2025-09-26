from unittest.mock import patch

import responses
from django.core.cache import cache
from django.test import TestCase, override_settings

from exchange.accounts.models import User, UserSms
from exchange.base.models import Settings
from exchange.broker.broker.schema import SMSSchema


class ProducerSMSTest(TestCase):
    def setUp(self):
        self.mobile = '09151234567'
        self.user = User.objects.create_user(username='test-user1', mobile=self.mobile)
        Settings.set('is_kafka_enabled', 'true')

    def mock_requests(self):
        responses.post('http://restfulsms.com/api/Token', json={'TokenKey': 'TestTokenKey'}, status=200)
        responses.post('http://restfulsms.com/api/UltraFastSend', json={'IsSuccessful': True}, status=200)
        responses.post('http://restfulsms.com/api/MessageSend', json={'IsSuccessful': True}, status=200)

    @responses.activate
    @override_settings(IS_PROD=True)
    @patch('exchange.accounts.producer.notification_producer.write_event')
    def test_sms_producer_fast_sms_topic(self, mock_producer):
        cache.set('settings_is_sms_logging_enabled', 'true')
        self.mock_requests()
        user_sms = UserSms.objects.create(
            user=self.user,
            tp=UserSms.TYPES.tfa_enable,
            to=self.mobile,
            text='Msg1',
            template=1,
        )
        sms = SMSSchema(
            user_id=str(self.user.uid),
            text=user_sms.text,
            tp=user_sms.tp,
            to=user_sms.to,
            template=user_sms.template,
        )
        mock_producer.assert_called_once_with('fast_sms', sms.serialize())

    @responses.activate
    @override_settings(IS_PROD=True)
    @patch('exchange.accounts.producer.notification_producer.write_event')
    def test_sms_producer_sms_topic(self, mock_producer):
        self.mock_requests()
        user_sms = UserSms.objects.create(
            user=self.user,
            tp=UserSms.TYPES.manual,
            to=self.mobile,
            text='Msg1',
            template=0,
        )
        sms = SMSSchema(
            user_id=str(self.user.uid),
            text=user_sms.text,
            tp=user_sms.tp,
            to=user_sms.to,
            template=user_sms.template,
        )
        mock_producer.assert_called_once_with('sms', sms.serialize())

    @responses.activate
    @override_settings(IS_PROD=True)
    @patch('exchange.accounts.producer.notification_producer.write_event')
    def test_sms_producer_sms_topic_without_user(self, mock_producer):
        self.mock_requests()
        user_sms = UserSms.objects.create(
            user=None,
            tp=UserSms.TYPES.manual,
            to=self.mobile,
            text='Msg1',
            template=0,
        )
        sms = SMSSchema(
            user_id=None,
            text=user_sms.text,
            tp=user_sms.tp,
            to=user_sms.to,
            template=user_sms.template,
        )
        mock_producer.assert_called_once_with('sms', sms.serialize())
