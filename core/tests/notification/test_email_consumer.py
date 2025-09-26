from datetime import datetime, timezone
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase

from exchange.broker.broker.schema import EmailSchema
from exchange.notification.consumers import email_callback
from exchange.notification.models import EmailInfo


class ConsumerEmailTest(TestCase):
    @patch('exchange.base.emailmanager.NotificationConfig.is_email_logging_enabled', return_value=True)
    @patch('exchange.base.emailmanager.NotificationConfig.is_email_broker_enabled', return_value=True)
    @patch('exchange.notification.email.email_manager.EmailManager.send_email')
    def test_consume_email_broker(self, mock_email_manager, *_):
        input_email_notifs = [
            EmailSchema(
                to='test1@nobitex.com',
                template='template',
                context={'test': 1},
                priority=settings.EMAIL_DEFAULT_PRIORITY,
                backend='backend',
                scheduled_time=datetime.now(timezone.utc),
            ),
            EmailSchema(
                to='test1@nobitex.com',
                template='template',
                context={'test': 2},
                priority=settings.EMAIL_DEFAULT_PRIORITY,
                backend='backend',
                scheduled_time=datetime.now(timezone.utc),
            ),
            EmailSchema(
                to='test1@nobitex.com',
                template='template',
                context={'test': 3},
                priority=settings.EMAIL_DEFAULT_PRIORITY,
                backend='backend',
                scheduled_time=datetime.now(timezone.utc),
            ),
            EmailSchema(
                to='test2@nobitex.com',
                template='template',
                context={'test': 4},
                priority=settings.EMAIL_DEFAULT_PRIORITY,
                backend='backend',
                scheduled_time=datetime.now(timezone.utc),
            ),
        ]
        for input_email_notif in input_email_notifs:
            email_callback(input_email_notif, ack=lambda: None)
        assert EmailInfo.objects.filter(to='test1@nobitex.com').count() == 3
        assert EmailInfo.objects.filter(to='test2@nobitex.com').count() == 1
        assert EmailInfo.objects.count() == 4
        assert mock_email_manager.call_count == 4

    @patch('exchange.base.emailmanager.NotificationConfig.is_email_logging_enabled', return_value=True)
    @patch('exchange.base.emailmanager.NotificationConfig.is_email_broker_enabled', return_value=False)
    @patch('exchange.notification.email.email_manager.EmailManager.send_email')
    def test_consume_email_broker_when_switch_is_off(self, mock_email_manager, *_):
        input_email_notifs = [
            EmailSchema(
                to='test1@nobitex.com',
                template='template',
                context={'test': 1},
                priority=settings.EMAIL_DEFAULT_PRIORITY,
                backend='backend',
                scheduled_time=datetime.now(timezone.utc),
            ),
            EmailSchema(
                to='test1@nobitex.com',
                template='template',
                context={'test': 2},
                priority=settings.EMAIL_DEFAULT_PRIORITY,
                backend='backend',
                scheduled_time=datetime.now(timezone.utc),
            ),
            EmailSchema(
                to='test1@nobitex.com',
                template='template',
                context={'test': 3},
                priority=settings.EMAIL_DEFAULT_PRIORITY,
                backend='backend',
                scheduled_time=datetime.now(timezone.utc),
            ),
            EmailSchema(
                to='test2@nobitex.com',
                template='template',
                context={'test': 4},
                priority=settings.EMAIL_DEFAULT_PRIORITY,
                backend='backend',
                scheduled_time=datetime.now(timezone.utc),
            ),
        ]
        for input_email_notif in input_email_notifs:
            email_callback(input_email_notif, ack=lambda: None)
        assert EmailInfo.objects.filter(to='test1@nobitex.com').count() == 3
        assert EmailInfo.objects.filter(to='test2@nobitex.com').count() == 1
        assert EmailInfo.objects.count() == 4
        assert mock_email_manager.call_count == 0
