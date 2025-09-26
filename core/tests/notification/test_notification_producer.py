from unittest.mock import patch
from uuid import uuid4

from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import Notification, User


class ProducerNotificationTest(TestCase):
    def setUp(self):
        self.UID_1 = uuid4()
        self.UID_2 = uuid4()

        self.user1 = User.objects.create_user(username='test-user1', uid=self.UID_1, telegram_conversation_id='test1')
        self.user2 = User.objects.create_user(username='test-user2', uid=self.UID_2, telegram_conversation_id='test2')

        cache.set('settings_kafka_broker_enabled', 'true')
        cache.set('settings_is_notification_logging_enabled', 'true')
        cache.set('settings_is_notification_broker_enabled', 'true')

    @patch('exchange.accounts.producer.notification_producer.write_event')
    def test_producer_notif_broker(self, producer_write_event):
        Notification.objects.create(
            user=self.user1,
            message='msg1',
            sent_to_telegram=True,
            sent_to_fcm=True,
        )
        producer_write_event.assert_called_once()

    @patch('exchange.accounts.models.Settings.get_value', return_value='true')
    @patch('exchange.accounts.models.send_telegram_message')
    @patch('exchange.accounts.producer.notification_producer.write_event')
    def test_send_notification_in_queue(self, producer_write_event, send_telegram_message, switch_mock):

        notifications = [
            Notification(
                user=self.user1,
                message='test_msg10',
                sent_to_telegram=True,
                sent_to_fcm=False,
            ),
            Notification(
                user=self.user1,
                message='test_msg10',
                sent_to_telegram=False,
                sent_to_fcm=True,
            ),
            Notification(
                user=self.user1,
                message='test_msg10',
                sent_to_telegram=True,
                sent_to_fcm=True,
            ),
        ]
        Notification.objects.bulk_create(notifications)
        assert Notification.objects.filter(message='test_msg10').count() == 3
        assert producer_write_event.call_count == len(notifications)
        assert send_telegram_message.call_count == 0
        Notification.objects.create(
            user=self.user1,
            message='test_msg15',
            sent_to_telegram=True,
            sent_to_fcm=True,
        )
        assert Notification.objects.filter(message='test_msg15').count() == 1
        assert producer_write_event.call_count == len(notifications) + 1
        assert send_telegram_message.call_count == 0

    @patch('exchange.accounts.models.send_telegram_message.chunks')
    @patch('exchange.accounts.producer.notification_producer.write_event')
    def test_send_notification_directly(self, producer_write_event, send_telegram_message):
        cache.set('settings_is_notification_broker_enabled', 'false')
        notifications = [
            Notification(
                user=self.user1,
                message='test_msg1',
                sent_to_telegram=True,
                sent_to_fcm=True,
            ),
            Notification(
                user=self.user1,
                message='test_msg1',
                sent_to_telegram=True,
                sent_to_fcm=True,
            ),
            Notification(
                user=self.user1,
                message='test_msg1',
                sent_to_telegram=True,
                sent_to_fcm=True,
            ),
        ]

        Notification.objects.bulk_create(notifications)
        assert Notification.objects.filter(message='test_msg1').count() == 3
        assert producer_write_event.call_count == 3
        assert send_telegram_message.call_count == 1
        Notification.objects.create(
            user=self.user1,
            message='test_msg15',
            sent_to_telegram=True,
            sent_to_fcm=True,
        )
        assert Notification.objects.filter(message='test_msg15').count() == 1
        assert producer_write_event.call_count == len(notifications) + 1
        assert send_telegram_message.call_count == 1

    @patch('exchange.accounts.models.send_telegram_message.chunks')
    @patch('exchange.accounts.producer.notification_producer.write_event')
    def test_send_notification_directly_when_kafka_is_disabled(self, producer_write_event, send_telegram_message):
        cache.set('settings_kafka_broker_enabled', 'false')
        cache.set('settings_is_notification_broker_enabled', 'false')
        notifications = [
            Notification(
                user=self.user1,
                message='test_msg1',
                sent_to_telegram=True,
                sent_to_fcm=True,
            ),
            Notification(
                user=self.user1,
                message='test_msg1',
                sent_to_telegram=True,
                sent_to_fcm=True,
            ),
            Notification(
                user=self.user1,
                message='test_msg1',
                sent_to_telegram=True,
                sent_to_fcm=True,
            ),
        ]

        Notification.objects.bulk_create(notifications)
        assert Notification.objects.filter(message='test_msg1').count() == 3
        assert producer_write_event.call_count == 0
        assert send_telegram_message.call_count == 1
        Notification.objects.create(
            user=self.user1,
            message='test_msg15',
            sent_to_telegram=True,
            sent_to_fcm=True,
        )
        assert Notification.objects.filter(message='test_msg15').count() == 1
        assert producer_write_event.call_count == 0


class TelegramNotificationProducerTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(id=202)
        self.user.telegram_conversation_id = 'test'
        self.user.save()

        cache.set('settings_kafka_broker_enabled', 'true')
        cache.set('settings_is_notification_broker_enabled', 'true')
        cache.set('settings_is_notification_logging_enabled', 'true')

    @patch('exchange.accounts.models.send_telegram_message.apply_async')
    @patch('exchange.accounts.producer.notification_producer.write_event')
    def test_send_telegram_message_directly(self, producer_write_event, send_telegram_message):
        cache.set('settings_kafka_broker_enabled', 'false')
        cache.set('settings_is_notification_broker_enabled', 'false')
        notification = Notification(user=self.user, message='test_msg1')
        notification.send_to_telegram_conversation(save=False, is_otp=False)
        assert producer_write_event.call_count == 0
        assert send_telegram_message.call_count == 1
        notification.send_to_telegram_conversation(save=False, is_otp=True)
        assert producer_write_event.call_count == 0
        assert send_telegram_message.call_count == 2

    @patch('exchange.accounts.models.send_telegram_message.apply_async')
    @patch('exchange.accounts.producer.notification_producer.write_event')
    def test_send_telegram_message_in_queue(self, producer_write_event, send_telegram_message):
        notification = Notification(user=self.user, message='test_msg1')
        notification.send_to_telegram_conversation(save=False, is_otp=False)
        assert producer_write_event.call_count == 1
        assert send_telegram_message.call_count == 0
        notification.send_to_telegram_conversation(save=False, is_otp=True)
        assert producer_write_event.call_count == 2
        assert send_telegram_message.call_count == 0

    @patch('exchange.accounts.models.send_telegram_message.apply_async')
    @patch('exchange.accounts.producer.notification_producer.write_event')
    def test_notify_admin_directly(self, producer_write_event, send_telegram_message):
        cache.set('settings_kafka_broker_enabled', 'false')
        cache.set('settings_is_notification_broker_enabled', 'false')
        Notification.notify_admins('test_msg1')
        assert producer_write_event.call_count == 0
        assert send_telegram_message.call_count == 1

    @patch('exchange.accounts.models.send_telegram_message.apply_async')
    @patch('exchange.accounts.producer.notification_producer.write_event')
    def test_notify_admin_in_queue(self, producer_write_event, send_telegram_message):
        Notification.notify_admins('test_msg1')
        assert producer_write_event.call_count == 1
        assert send_telegram_message.call_count == 0
