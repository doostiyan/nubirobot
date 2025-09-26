from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings

from exchange.accounts.models import Notification
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.socialtrade.crons import SendPreRenewalNotifCron
from exchange.socialtrade.tasks import (
    send_pre_renewal_alert,
    task_send_email,
    task_send_mass_emails,
    task_send_mass_notifications,
    task_send_mass_sms,
)
from tests.socialtrade.helpers import SocialTradeMixin, enable_email


@patch.object(task_send_mass_sms, 'delay', task_send_mass_sms)
@patch.object(task_send_mass_notifications, 'delay', task_send_mass_notifications)
@patch.object(task_send_mass_emails, 'delay', task_send_mass_emails)
@patch.object(task_send_email, 'delay', task_send_email)
@patch.object(send_pre_renewal_alert, 'delay', send_pre_renewal_alert)
class SendPreRenewalNotifCronTest(SocialTradeMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        vp = self.user.get_verification_profile()
        vp.mobile_confirmed = True
        vp.email_confirmed = True
        vp.save()

        self.leader = self.create_leader(subscription_currency=Currencies.usdt, fee=Decimal('10.56'))
        self.candid_subscription = self.create_subscription(user=self.user, leader=self.leader)
        self.candid_subscription.expires_at = ir_now() + timedelta(days=1)
        self.candid_subscription.save()
        self.candid_subscription.leader.refresh_from_db()

        self.not_candid_subscription1 = self.create_subscription(user=self.user)
        self.not_candid_subscription1.expires_at = ir_now()
        self.not_candid_subscription1.save()

        self.not_candid_subscription2 = self.create_subscription(user=self.user)
        self.not_candid_subscription2.expires_at = ir_now() + timedelta(days=2)
        self.not_candid_subscription2.save()

        Notification.objects.all().delete()

    def test_send_pre_renewal_notif_trial(self):
        self.candid_subscription.is_trial = True
        self.candid_subscription.save()

        SendPreRenewalNotifCron().run()

        notifications = Notification.objects.filter(user=self.user)
        assert notifications.count() == 1
        notification = notifications.first()
        assert notification.message == (
            f'اشتراک آزمایشی شما در حال اتمام است. '
            f'درصورت داشتن موجودی، اشتراک شما به صورت خودکار فعال خواهد شد.\n'
            f'تریدر: {self.candid_subscription.leader.nickname}\n'
            f'زمان پایان اشتراک آزمایشی : {self.candid_subscription.shamsi_expire_date}\n'
            f'هزینه اشتراک: 10.56 تتر'
        )

    def test_send_pre_renewal_notif_subscription_auto(self):
        self.candid_subscription.is_trial = False
        self.candid_subscription.is_auto_renewal_enabled = True
        self.candid_subscription.save()

        SendPreRenewalNotifCron().run()

        notifications = Notification.objects.filter(user=self.user)
        assert notifications.count() == 1
        notification = notifications.first()
        assert notification.message == (
            f'اشتراک تریدر انتخابی شما در تاریخ {self.candid_subscription.shamsi_expire_date} به پایان میرسد '
            f'و به صورت خودکار برای دوره بعد تمدید خواهد شد. '
            f'درصورت تمایل به تغییر در عملیات تمدید به پنل کاربری خود مراجعه نمایید.\n'
            f'تریدر: {self.candid_subscription.leader.nickname}\n'
            f'هزینه اشتراک: 10.56 تتر'
        )

    def test_send_pre_renewal_notif_subscription_non_auto(self):
        self.candid_subscription.is_trial = False
        self.candid_subscription.is_auto_renewal_enabled = False
        self.candid_subscription.save()

        SendPreRenewalNotifCron().run()

        notifications = Notification.objects.filter(user=self.user)
        assert notifications.count() == 1
        notification = notifications.first()
        assert notification.message == (
            f'اشتراک تریدر انتخابی شما در تاریخ {self.candid_subscription.shamsi_expire_date} به پایان میرسد، '
            f'درصورت تمایل برای تمدید اشتراک به پنل کاربری خود مراجعه نمایید.\n'
            f'تریدر: {self.candid_subscription.leader.nickname}\n'
            f'هزینه اشتراک: 10.56 تتر'
        )

    def test_send_pre_renewal_notif_when_leader_deleted(self):
        self.candid_subscription.leader.deleted_at = ir_now()
        self.candid_subscription.leader.save()
        SendPreRenewalNotifCron().run()

        notifications = Notification.objects.filter(user=self.user)
        assert notifications.count() == 0

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_send_pre_renewal_notif_trial_email(self):
        self.candid_subscription.is_trial = True
        self.candid_subscription.save()

        with enable_email(self.user):
            send_pre_renewal_alert(self.candid_subscription.pk)

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_send_pre_renewal_notif_subscription_auto_email(self):
        self.candid_subscription.is_trial = False
        self.candid_subscription.is_auto_renewal_enabled = True
        self.candid_subscription.save()

        with enable_email(self.user):
            send_pre_renewal_alert(self.candid_subscription.pk)

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_send_pre_renewal_notif_subscription_non_auto_email(self):
        self.candid_subscription.is_trial = False
        self.candid_subscription.is_auto_renewal_enabled = False
        self.candid_subscription.save()

        with enable_email(self.user):
            send_pre_renewal_alert(self.candid_subscription.pk)
