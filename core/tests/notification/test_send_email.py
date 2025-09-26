from datetime import datetime
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from post_office.models import Email

from exchange.accounts.models import AntiPhishing, User  # coupling to core
from exchange.base.calendar import to_shamsi_date
from exchange.base.models import Settings
from exchange.notification.email.email_manager import EmailManager


class TestSendEmail(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(id=201)
        cache.set('settings_kafka_broker_enabled', 'true')
        Settings.set('is_enabled_broker_email', 'true')

    @pytest.mark.slow
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_anti_phishing_code_email(self):
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('new_update_email_templates')
        anti_phishing = AntiPhishing.objects.create(user=self.user, code='123$@456#&', is_active=True)
        EmailManager.send_email(
            email=self.user.email,
            template='login_notif',
            data={
                'successful': True,
                'username': 'testalikafytest',
                'ip': '192.168.127.12',
                'date': to_shamsi_date(datetime.now()),
                'device': 'unknown',
            },
        )
        with patch('django.db.connection.close'):
            call_command('send_queued_mail')
        email = Email.objects.filter(to=self.user.email, subject='ورود به نوبیتکس').last()
        assert anti_phishing.code in email.html_message
