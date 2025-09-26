from unittest.mock import call, patch
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import User
from exchange.broker.broker.schema.notification import (
    AdminTelegramNotificationSchema,
    NotificationSchema,
    TelegramNotificationSchema,
)
from exchange.notification.consumers import (
    admin_telegram_callback,
    fast_telegram_callback,
    notif_callback,
    telegram_callback,
)
from exchange.notification.models import InAppNotification

UID_1 = uuid4()
UID_2 = uuid4()


class ConsumerNotificationTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='test-user1', telegram_conversation_id='user1')
        self.user1.uid = UID_1
        self.user1.save()

        self.user2 = User.objects.create_user(username='test-user2', uid=UID_2, telegram_conversation_id='user2')
        self.user2.uid = UID_2
        self.user2.save()
        cache.set('settings_kafka_broker_enabled', 'true')
        cache.set('settings_is_notification_broker_enabled', 'true')

    @patch('exchange.notification.models.in_app_notification.send_telegram_message.apply_async')
    def test_consume_notif_broker(self, mock_send_telegram_message):
        InAppNotification.objects.all().delete()

        input_notifs = [
            NotificationSchema(
                user_id=str(UID_1),
                message='msg1',
                admin=str(UID_1),
                sent_to_telegram=True,
                sent_to_fcm=True,
            ),
            NotificationSchema(
                user_id=str(UID_1),
                message='msg2',
                admin=str(UID_1),
                sent_to_telegram=True,
                sent_to_fcm=True,
            ),
            NotificationSchema(
                user_id=str(UID_2),
                message='msg3',
                admin=str(UID_1),
                sent_to_telegram=True,
                sent_to_fcm=True,
            ),
            NotificationSchema(
                user_id=str(uuid4()),
                message='invalid-uid',
                admin=str(UID_1),
                sent_to_telegram=True,
                sent_to_fcm=True,
            ),
        ]
        for input_notif in input_notifs:
            notif_callback(input_notif, ack=lambda: None)

        assert InAppNotification.objects.filter(user__uid=UID_1).count() == 2
        assert InAppNotification.objects.filter(user__uid=UID_2).count() == 1
        notification = InAppNotification.objects.get(user__uid=UID_2)
        assert notification.message == 'msg3'
        assert notification.admin == self.user1
        assert notification.sent_to_telegram == True
        assert notification.sent_to_fcm == True

        assert InAppNotification.objects.count() == 3
        assert mock_send_telegram_message.call_count == 3

    @patch('exchange.notification.models.in_app_notification.send_telegram_message.apply_async')
    def test_consume_notif_send_telegram_message(self, mock_send_telegram_message):
        InAppNotification.objects.all().delete()
        input_notif = NotificationSchema(
                user_id=str(UID_1),
                message='msg1',
                admin=str(UID_1),
                sent_to_telegram=True,
                sent_to_fcm=True,
            )

        notif_callback(input_notif, ack=lambda: None)

        notification = InAppNotification.objects.filter(user__uid=UID_1).first()
        mock_send_telegram_message.assert_called_once_with(
            (notification.get_telegram_text(), self.user1.telegram_conversation_id),
            expires=InAppNotification.TELEGRAM_TASK_TIMEOUT,
            queue=settings.TELEGRAM_CELERY_QUEUE,
        )

    @patch('exchange.notification.models.in_app_notification.send_telegram_message.apply_async')
    def test_consume_telegram_message(self, mock_send_telegram_message):
        input_telegram_notifs = [
            TelegramNotificationSchema(
                user_id=str(UID_1),
                message='msg1',
                title='title_test',
            ),
            TelegramNotificationSchema(
                user_id=str(UID_1),
                message='msg2',
            ),
        ]

        for input_telegram_notif in input_telegram_notifs:
            telegram_callback(input_telegram_notif, ack=lambda: None)

        mock_send_telegram_message.assert_has_calls(
            calls=[
                call(('*title_test*\nmsg1', 'user1'), expires=1800, queue=settings.TELEGRAM_CELERY_QUEUE),
                call(('*🔵 Notification*\nmsg2', 'user1'), expires=1800, queue=settings.TELEGRAM_CELERY_QUEUE),
            ]
        )

    @patch('exchange.notification.models.in_app_notification.send_telegram_message.apply_async')
    def test_consume_fast_telegram_message(self, mock_send_telegram_message):
        input_fast_telegram_notifs = [
            TelegramNotificationSchema(
                user_id=str(UID_1),
                message='msg1',
                title='title_test',
            ),
            TelegramNotificationSchema(
                user_id=str(UID_1),
                message='msg2',
            ),
        ]

        for input_fast_telegram_notif in input_fast_telegram_notifs:
            fast_telegram_callback(input_fast_telegram_notif, ack=lambda: None)

        mock_send_telegram_message.assert_has_calls(
            calls=[
                call(('*title_test*\nmsg1', 'user1'), expires=1800, queue=settings.TELEGRAM_CELERY_QUEUE),
                call(('*🔵 Notification*\nmsg2', 'user1'), expires=1800, queue=settings.TELEGRAM_CELERY_QUEUE),
            ]
        )

    @patch('exchange.notification.models.in_app_notification.send_telegram_message.apply_async')
    def test_consume_admin_telegram_message(self, mock_send_telegram_message):
        input_admin_telegram_notifs = [
            AdminTelegramNotificationSchema(
                message='msg1',
            ),
            AdminTelegramNotificationSchema(
                message='msg2',
                title='title',
                channel='al',
                message_id='ik',
                codename='afy',
                cache_key='test',
                cache_timeout=10,
            ),
        ]

        for input_admin_telegram_notif in input_admin_telegram_notifs:
            admin_telegram_callback(input_admin_telegram_notif, ack=lambda: None)

        mock_send_telegram_message.assert_has_calls(
            calls=[
                call(
                    ('*🔵 Notification*\nmsg1', '-1001379604352'),
                    {'message_id': None, 'pin': False, 'cache_key': None, 'cache_timeout': None},
                    expires=1200,
                    queue=settings.TELEGRAM_ADMIN_CELERY_QUEUE,
                ),
                call(
                    ('*title*\nmsg2', '-267453237'),
                    {'message_id': 'ik', 'pin': False, 'cache_key': 'test', 'cache_timeout': 10},
                    expires=1200,
                    queue=settings.TELEGRAM_ADMIN_CELERY_QUEUE,
                ),
            ]
        )

    @patch('exchange.notification.models.in_app_notification.send_telegram_message.apply_async')
    def test_consume_telegram_message_when_switch_is_off(self, mock_send_telegram_message):
        cache.set('settings_is_notification_broker_enabled', 'false')
        input_telegram_notifs = [
            TelegramNotificationSchema(
                user_id=str(UID_1),
                message='msg1',
                title='title_test',
            ),
            TelegramNotificationSchema(
                user_id=str(UID_1),
                message='msg2',
            ),
        ]
        for input_telegram_notif in input_telegram_notifs:
            fast_telegram_callback(input_telegram_notif, ack=lambda: None)
        mock_send_telegram_message.assert_not_called()

    @patch('exchange.notification.models.in_app_notification.send_telegram_message.apply_async')
    def test_consume_notif_when_switch_is_off(self, mock_send_telegram_message):
        InAppNotification.objects.all().delete()
        cache.set('settings_is_notification_broker_enabled', 'false')
        input_notif = NotificationSchema(
                user_id=str(UID_1),
                message='msg1',
                admin=str(UID_1),
                sent_to_telegram=True,
                sent_to_fcm=True,
            )
        notif_callback(input_notif, ack=lambda: None)
        assert InAppNotification.objects.filter(user__uid=UID_1).exists()
        mock_send_telegram_message.assert_not_called()

    @patch('exchange.notification.models.in_app_notification.send_telegram_message.apply_async')
    def test_consume_admin_telegram_message_when_switch_is_off(self, mock_send_telegram_message):
        cache.set('settings_is_notification_broker_enabled', 'false')
        intput_admin_telegram_notif = AdminTelegramNotificationSchema(message='msg1')
        admin_telegram_callback(intput_admin_telegram_notif, ack=lambda: None)
        mock_send_telegram_message.assert_not_called()
