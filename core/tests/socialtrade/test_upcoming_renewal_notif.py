from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import TestCase, override_settings

from exchange.accounts.models import Notification
from exchange.base.calendar import ir_now
from exchange.base.constants import ZERO
from exchange.base.models import RIAL, Currencies, Settings
from exchange.socialtrade.crons import SendUpcomingRenewalNotifCron
from exchange.socialtrade.tasks import task_send_email
from exchange.wallet.models import Wallet
from tests.base.utils import create_order
from tests.socialtrade.helpers import SocialTradeMixin


class SendUpcomingRenewalNotifCronTest(SocialTradeMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.other_user = self.create_user()
        vp = self.user.get_verification_profile()
        vp.mobile_confirmed = True
        vp.email_confirmed = True
        vp.save()

        self.user_wallet = self.charge_wallet(self.user, RIAL, 1000000)
        self.candid_subscription = self.create_subscription(
            user=self.user,
            fee=14000,
            is_trial=False,
            is_auto_renewal_enabled=True,
        )
        self.candid_subscription.expires_at = ir_now() + timedelta(minutes=31)
        self.candid_subscription.save()
        self.candid_subscription.leader.refresh_from_db()

        Notification.objects.all().delete()

    def test_send_upcoming_renewal_notif(self):
        SendUpcomingRenewalNotifCron().run()

        notifications = Notification.objects.filter(user=self.user)
        assert notifications.count() == 1
        notification = notifications.first()
        assert notification.message == (
            f'کاربر گرامی، اشتراک سوشال ترید شما در تاریخ {self.candid_subscription.shamsi_expire_date} تمدید خواهد شد.\n'
            f'تریدر: {self.candid_subscription.leader.nickname}\n'
            f'هزینه اشتراک: 1,400 تومان'
        )

    def test_not_send_upcoming_renewal_notif_on_zero_fee(self):
        self.candid_subscription.leader.subscription_fee = ZERO
        self.candid_subscription.leader.save()

        SendUpcomingRenewalNotifCron().run()

        notifications = Notification.objects.filter(user=self.user)
        assert notifications.count() == 0

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    @patch.object(task_send_email, 'delay', task_send_email)
    def test_send_upcoming_renewal_email(self):
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')

        SendUpcomingRenewalNotifCron().run()

        with patch('django.db.connection.close'):
            call_command('send_queued_mail')

    def test_send_upcoming_renewal_notif_when_leader_deleted(self):
        self.candid_subscription.leader.deleted_at = ir_now()
        self.candid_subscription.leader.save()

        SendUpcomingRenewalNotifCron().run()

        notifications = Notification.objects.filter(user=self.user)
        assert notifications.count() == 0

    def test_send_upcoming_renewal_notif_when_canceled(self):
        self.candid_subscription.canceled_at = ir_now()
        self.candid_subscription.save()

        SendUpcomingRenewalNotifCron().run()

        notifications = Notification.objects.filter(user=self.user)
        assert notifications.count() == 0

    def test_send_upcoming_renewal_notif_when_is_renewed(self):
        self.candid_subscription.is_renewed = True
        self.candid_subscription.save()

        SendUpcomingRenewalNotifCron().run()

        notifications = Notification.objects.filter(user=self.user)
        assert notifications.count() == 0

    def test_send_upcoming_renewal_notif_when_expires_at_too_late(self):
        self.candid_subscription.expires_at = ir_now() + timedelta(minutes=91)
        self.candid_subscription.save()

        SendUpcomingRenewalNotifCron().run()

        notifications = Notification.objects.filter(user=self.user)
        assert notifications.count() == 0

    def test_send_upcoming_renewal_notif_when_expires_at_too_soon(self):
        self.candid_subscription.expires_at = ir_now() + timedelta(minutes=29)
        self.candid_subscription.save()

        SendUpcomingRenewalNotifCron().run()

        notifications = Notification.objects.filter(user=self.user)
        assert notifications.count() == 0

    def test_send_upcoming_renewal_notif_when_is_trial(self):
        self.candid_subscription.is_trial = True
        self.candid_subscription.save()

        SendUpcomingRenewalNotifCron().run()

        notifications = Notification.objects.filter(user=self.user)
        assert notifications.count() == 0

    def test_send_upcoming_renewal_notif_when_auto_renew_is_off(self):
        self.candid_subscription.is_auto_renewal_enabled = False
        self.candid_subscription.save()

        SendUpcomingRenewalNotifCron().run()

        notifications = Notification.objects.filter(user=self.user)
        assert notifications.count() == 0

    def test_send_upcoming_renewal_notif_when_wallet_balance_is_insufficient_for_renew(self):
        # when balance is not enough
        self.user_wallet.balance = 0
        self.user_wallet.save()
        self.charge_wallet(self.user, RIAL, 1000000, tp=Wallet.WALLET_TYPE.margin)

        SendUpcomingRenewalNotifCron().run()

        notifications = Notification.objects.filter(user=self.user)
        assert notifications.count() == 0

        # when balance is blocked
        self.charge_wallet(self.user, RIAL, 14000, tp=Wallet.WALLET_TYPE.spot)
        create_order(self.user, Currencies.usdt, Currencies.rls, Decimal('0.5'), Decimal('140e7'), sell=False)
        self.charge_wallet(self.user, RIAL, Decimal('-0.5') * Decimal('140e7'), tp=Wallet.WALLET_TYPE.spot)
        self.user_wallet.refresh_from_db()

        assert self.user_wallet.currency == self.candid_subscription.leader.subscription_currency
        assert self.user_wallet.active_balance < self.candid_subscription.leader.subscription_fee
        assert self.user_wallet.balance == self.candid_subscription.leader.subscription_fee

        SendUpcomingRenewalNotifCron().run()

        notifications = Notification.objects.filter(user=self.user)
        assert notifications.count() == 0
