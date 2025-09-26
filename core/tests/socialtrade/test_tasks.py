import decimal
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import Notification, User, UserSms
from exchange.base.api import ParseError
from exchange.base.models import Currencies, Settings, get_currency_codename
from exchange.base.templatetags.nobitex import currencyformat
from exchange.socialtrade.exceptions import SubscriptionFeeIsLessThanTheMinimum, SubscriptionFeeIsMoreThanTheMaximum
from exchange.socialtrade.tasks import (
    change_subscription_fee,
    task_send_mass_emails,
    task_send_mass_notifications,
    task_send_mass_sms,
)
from exchange.socialtrade.validators import FEE_BOUNDARY_KEY
from tests.socialtrade.helpers import SocialTradeMixin


class SendMassSMSTest(TestCase):
    def setUp(self) -> None:
        self.verifications = [{}, {'mobile': True}]
        self.users = self._create_users(2, self.verifications)
        self.users_ids = [user.id for user in self.users]
        self.sms_tp = UserSms.TYPES.social_trade_notify_leader_of_deletion
        self.sms_template = UserSms.TEMPLATES.social_trade_notify_leader_of_deletion
        self.sms_text = 'test'

    def test_send_mass_sms(self):
        # Should send sms to 1 of the 2 users with verified mobile
        task_send_mass_sms.apply(args=(self.users_ids, self.sms_tp, self.sms_text, self.sms_template))
        assert UserSms.objects.all().count() == 1
        assert UserSms.objects.filter(user=self.users[0]).count() == 0
        assert UserSms.objects.filter(user=self.users[1]).count() == 1

    def _create_users(self, num: int, verifications: [dict]) -> [User]:
        User.objects.filter(username__contains='user_').delete()
        users = [
            User(
                username=f'user_{i + 1}',
                email=f'user_{i + 1}@gmail.com',
                mobile='09121234567',
            )
            for i in range(num)
        ]
        users = User.objects.bulk_create(users)
        if verifications:
            for user, verification in zip(users, verifications):
                vp = user.get_verification_profile()
                vp.mobile_confirmed = verification.get('mobile', False)
                vp.save()
        return users


class SendMassNotificationsTest(TestCase):
    def setUp(self) -> None:
        self.users = self._create_users(2)
        self.users_ids = [user.id for user in self.users]
        self.notification_message = 'TestNotification'

    def test_send_mass_notifications(self):
        # Should send notifications to both users
        Notification.objects.all().delete()
        task_send_mass_notifications.apply(args=(self.users_ids, self.notification_message))
        assert Notification.objects.all().count() == 2
        assert Notification.objects.filter(user=self.users[0], message=self.notification_message).count() == 1
        assert Notification.objects.filter(user=self.users[1], message=self.notification_message).count() == 1

    def _create_users(self, num: int) -> [User]:
        User.objects.filter(username__contains='user_').delete()
        users = [
            User(
                username=f'user_{i + 1}',
                email=f'user_{i + 1}@gmail.com',
                mobile='09121234567',
            )
            for i in range(num)
        ]
        return User.objects.bulk_create(users)


class SendMassEmailTest(TestCase):
    def setUp(self) -> None:
        self.verifications = [{}, {'email': True}]
        self.users = self._create_users(2, self.verifications)
        self.users_ids = [user.id for user in self.users]
        self.email_template = 'socialtrade/social_trade_notify_subscribers_of_leader_deletion'
        self.email_data = {'trader': 'TestTrader'}

    @patch('exchange.socialtrade.tasks.task_send_email.delay')
    def test_send_mass_email(self, mock_task_send_email):
        # Should send email to 1 of the 2 users with verified email
        task_send_mass_emails.apply(args=([self.users_ids[0]], self.email_template, self.email_data))
        mock_task_send_email.assert_not_called()
        task_send_mass_emails.apply(args=([self.users_ids[1]], self.email_template, self.email_data))
        mock_task_send_email.assert_called_once_with(
            email=self.users[1].email, template=self.email_template, data=self.email_data
        )

    def _create_users(self, num: int, verifications: [dict]) -> [User]:
        User.objects.filter(username__contains='user_').delete()
        users = [
            User(
                username=f'user_{i + 1}',
                email=f'user_{i + 1}@gmail.com',
                mobile='09121234567',
            )
            for i in range(num)
        ]
        users = User.objects.bulk_create(users)
        if verifications:
            for user, verification in zip(users, verifications):
                vp = user.get_verification_profile()
                vp.email_confirmed = verification.get('email', False)
                vp.save()
        return users


class ChangeSubscriptionFeeTest(TestCase, SocialTradeMixin):
    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)
        self.user_2 = User.objects.get(pk=202)
        self.user_leader = User.objects.get(pk=203)
        self.leader = self.create_leader()
        self.subscription = self.create_subscription(self.user, self.leader)

        Settings.set_dict(FEE_BOUNDARY_KEY, settings.SOCIAL_TRADE['default_fee_boundary'])

        call_command('update_email_templates')

    @patch('exchange.socialtrade.tasks.task_send_mass_emails.delay')
    @patch('exchange.socialtrade.tasks.task_send_mass_notifications.delay')
    @patch.object(change_subscription_fee, 'delay', change_subscription_fee)
    def test_change_subscription_fee(self, mock_is_notif_enabled, mock_send_email):
        new_fee = decimal.Decimal(2000)
        change_subscription_fee(self.leader.id, new_fee)
        self.leader.refresh_from_db()
        assert self.leader.subscription_fee == new_fee
        self.subscription.refresh_from_db()
        assert self.subscription.fee_amount == 1000
        mock_is_notif_enabled.assert_called_once()
        mock_send_email.assert_called_once()

        self.leader.subscription_currency = Currencies.usdt
        self.leader.save()
        change_subscription_fee(self.leader.id, '1.23')
        self.leader.refresh_from_db()
        assert self.leader.subscription_fee == decimal.Decimal('1.23')

        # When fee has more precision than expected
        with pytest.raises(ParseError):
            change_subscription_fee(self.leader.id, '1.234')

    @patch('exchange.socialtrade.tasks.task_send_mass_emails.delay')
    @patch.object(task_send_mass_notifications, 'delay', task_send_mass_notifications)
    def test_notify_for_change_subscription_fee(self, mock_send_email):
        Notification.objects.all().delete()
        new_fee = decimal.Decimal(2000)
        change_subscription_fee.apply(args=(self.leader.id, new_fee))
        mock_send_email.assert_called_once()
        self.leader.refresh_from_db()
        message = (
            (
                'سوشال ترید: تغییر هزینه اشتراک \n '
                'کاربر گرامی، هزینه اشتراک سوشال ترید برای تریدر انتخابی شما در دوره بعدی با تغییر قیمت مواجه شده است. در صورت تمایل برای تغییر در اشتراک دوره بعدی به پنل کاربری مراجعه نمایید.\n '
                f'تریدر: {self.leader.nickname}\n'
                f'هزینه اشتراک: 200 تومان'
            ),
        )
        assert Notification.objects.filter(user=self.user)[0].message == message[0]

    def test_change_subscription_fee_with_low_fee(self):
        new_fee = (
            decimal.Decimal(
                Settings.get_dict(FEE_BOUNDARY_KEY)['min'][get_currency_codename(self.leader.subscription_currency)]
            )
            - 1
        )
        with pytest.raises(SubscriptionFeeIsLessThanTheMinimum):
            change_subscription_fee(leader_id=self.leader.id, new_fee=new_fee)

    def test_change_subscription_fee_with_high_fee(self):
        new_fee = (
            decimal.Decimal(
                Settings.get_dict(FEE_BOUNDARY_KEY)['max'][get_currency_codename(self.leader.subscription_currency)]
            )
            + 1
        )
        with pytest.raises(SubscriptionFeeIsMoreThanTheMaximum):
            change_subscription_fee(leader_id=self.leader.id, new_fee=new_fee)
