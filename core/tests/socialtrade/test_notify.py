from unittest.mock import patch

from django.test import TestCase

from exchange.accounts.models import Notification, User, UserSms
from exchange.socialtrade.notify import notify_mass_users, notify_user


class NotifyUserTest(TestCase):
    def setUp(self) -> None:
        self.verifications = [{}, {'mobile': True}, {'email': True}, {'mobile': True, 'email': True}]
        self.users = self._create_users(4, self.verifications)
        self.sms_tp = UserSms.TYPES.social_trade_notify_leader_of_deletion
        self.sms_template = UserSms.TEMPLATES.social_trade_notify_leader_of_deletion
        self.sms_text = 'test'
        self.notification_message = 'notification message'
        self.email_template = 'socialtrade/social_trade_notify_leader_of_deletion'
        self.email_data = {}

    @patch('exchange.socialtrade.notify.EmailManager.send_email')
    def test_notify_with_sms_and_notif_and_email(self, mock_send_email):
        # Should send notification to all 4 users,
        # send sms to 2 users with verified mobiles and send email to 2 users with verified email
        for user, verification in zip(self.users, self.verifications):
            notify_user(
                user=user,
                sms_tp=self.sms_tp,
                sms_template=self.sms_template,
                sms_text=self.sms_text,
                notification_message=self.notification_message,
                email_template=self.email_template,
                email_data=self.email_data,
            )
            if verification.get('mobile', False):
                assert (
                    UserSms.objects.filter(
                        user=user, tp=self.sms_tp, template=self.sms_template, text=self.sms_text
                    ).count()
                    == 1
                )
            if verification.get('email', False):
                mock_send_email.assert_called_with(
                    email=str(user.email),
                    template=self.email_template,
                    data=self.email_data,
                    priority='low',
                )
            assert Notification.objects.filter(user=user, message=self.notification_message).count() == 1
        assert UserSms.objects.all().count() == 2
        assert mock_send_email.call_count == 2
        assert Notification.objects.all().count() == 4

    @patch('exchange.socialtrade.notify.EmailManager.send_email')
    def test_notify_with_notif_and_email(self, mock_send_email):
        # Should send notification to all 4 users, send sms to no one and send email to 2 users with verified email
        for user, verification in zip(self.users, self.verifications):
            notify_user(
                user=user,
                sms_tp=None,
                sms_template=self.sms_template,
                sms_text=self.sms_text,
                notification_message=self.notification_message,
                email_template=self.email_template,
                email_data=self.email_data,
            )
            assert UserSms.objects.filter(user=user).count() == 0
            if verification.get('email', False):
                mock_send_email.assert_called_with(
                    email=str(user.email),
                    template=self.email_template,
                    data=self.email_data,
                    priority='low',
                )
            assert Notification.objects.filter(user=user, message=self.notification_message).count() == 1
        assert UserSms.objects.all().count() == 0
        assert mock_send_email.call_count == 2
        assert Notification.objects.all().count() == 4

    @patch('exchange.socialtrade.notify.EmailManager.send_email')
    def test_notify_with_sms_and_email(self, mock_send_email):
        # Should send notification to no one,
        # send sms to 2 users with verified mobiles and send email to 2 users with verified email
        for user, verification in zip(self.users, self.verifications):
            notify_user(
                user=user,
                sms_tp=self.sms_tp,
                sms_template=None,
                sms_text=self.sms_text,
                notification_message=None,
                email_template=self.email_template,
                email_data=self.email_data,
            )
            if verification.get('mobile', False):
                assert UserSms.objects.filter(user=user, tp=self.sms_tp, text=self.sms_text).count() == 1
            if verification.get('email', False):
                mock_send_email.assert_called_with(
                    email=str(user.email),
                    template=self.email_template,
                    data=self.email_data,
                    priority='low',
                )
            assert Notification.objects.filter(user=user).count() == 0
        assert UserSms.objects.all().count() == 2
        assert mock_send_email.call_count == 2
        assert Notification.objects.all().count() == 0

    @patch('exchange.socialtrade.notify.EmailManager.send_email')
    def test_notify_with_sms_and_notif(self, mock_send_email):
        # Should send notification to 4 users,
        # send sms to 2 users with verified mobiles and send email to no one
        for user, verification in zip(self.users, self.verifications):
            notify_user(
                user=user,
                sms_tp=self.sms_tp,
                sms_template=None,
                sms_text=self.sms_text,
                notification_message=self.notification_message,
                email_template=None,
                email_data=self.email_data,
            )
            if verification.get('mobile', False):
                assert UserSms.objects.filter(user=user, tp=self.sms_tp, text=self.sms_text).count() == 1
            mock_send_email.assert_not_called()
            assert Notification.objects.filter(user=user).count() == 1
        assert UserSms.objects.all().count() == 2
        assert mock_send_email.call_count == 0
        assert Notification.objects.all().count() == 4

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
                if 'mobile' in verification:
                    vp.mobile_confirmed = verification['mobile']
                if 'email' in verification:
                    vp.email_confirmed = verification['email']
                vp.save()
        Notification.objects.all().delete()
        return users


class NotifyMassUsersTest(TestCase):
    def setUp(self) -> None:
        self.users_ids = [1, 2]
        self.sms_tp = UserSms.TYPES.social_trade_notify_subscribers_of_leader_deletion
        self.sms_template = UserSms.TEMPLATES.social_trade_notify_subscribers_of_leader_deletion
        self.sms_text = 'test'
        self.notification_message = 'notification message'
        self.email_template = 'socialtrade/social_trade_notify_subscribers_of_leader_deletion'
        self.email_data = {'trader': 'TestTrader'}

    @patch('exchange.socialtrade.notify.task_send_mass_emails.delay')
    @patch('exchange.socialtrade.notify.task_send_mass_notifications.delay')
    @patch('exchange.socialtrade.notify.task_send_mass_sms.delay')
    def test_notify_with_sms_and_notif_and_email(self, mock_sms_task, mock_notification_task, mock_email_task):
        notify_mass_users(
            users_ids=[],
            sms_tps=self.sms_tp,
            notification_messages=self.notification_message,
            email_templates=self.email_template,
        )
        mock_sms_task.assert_called_once_with([], self.sms_tp, None, None)
        mock_notification_task.assert_called_once_with([], self.notification_message)
        mock_email_task.assert_called_once_with([], self.email_template, None)

    @patch('exchange.socialtrade.notify.task_send_mass_emails.delay')
    @patch('exchange.socialtrade.notify.task_send_mass_notifications.delay')
    @patch('exchange.socialtrade.notify.task_send_mass_sms.delay')
    def test_notify_with_sms_and_notif_and_email_with_data(
        self, mock_sms_task, mock_notification_task, mock_email_task
    ):
        notify_mass_users(
            users_ids=self.users_ids,
            sms_tps=self.sms_tp,
            sms_templates=self.sms_template,
            sms_texts=self.sms_text,
            notification_messages=self.notification_message,
            email_templates=self.email_template,
            email_data=self.email_data,
        )
        mock_sms_task.assert_called_once_with(self.users_ids, self.sms_tp, self.sms_text, self.sms_template)
        mock_notification_task.assert_called_once_with(self.users_ids, self.notification_message)
        mock_email_task.assert_called_once_with(self.users_ids, self.email_template, self.email_data)

    @patch('exchange.socialtrade.notify.task_send_mass_emails.delay')
    @patch('exchange.socialtrade.notify.task_send_mass_notifications.delay')
    @patch('exchange.socialtrade.notify.task_send_mass_sms.delay')
    def test_notify_with_sms_and_notif_with_data(self, mock_sms_task, mock_notification_task, mock_email_task):
        notify_mass_users(
            users_ids=self.users_ids,
            sms_tps=self.sms_tp,
            sms_templates=self.sms_template,
            sms_texts=None,
            notification_messages=self.notification_message,
            email_templates=None,
            email_data=self.email_data,
        )
        mock_sms_task.assert_called_once_with(self.users_ids, self.sms_tp, None, self.sms_template)
        mock_notification_task.assert_called_once_with(self.users_ids, self.notification_message)
        mock_email_task.assert_not_called()

    @patch('exchange.socialtrade.notify.task_send_mass_emails.delay')
    @patch('exchange.socialtrade.notify.task_send_mass_notifications.delay')
    @patch('exchange.socialtrade.notify.task_send_mass_sms.delay')
    def test_notify_with_sms_and_email_with_data(self, mock_sms_task, mock_notification_task, mock_email_task):
        notify_mass_users(
            users_ids=self.users_ids,
            sms_tps=self.sms_tp,
            sms_templates=self.sms_template,
            sms_texts=None,
            notification_messages=None,
            email_templates=self.email_template,
            email_data={},
        )
        mock_sms_task.assert_called_once_with(self.users_ids, self.sms_tp, None, self.sms_template)
        mock_notification_task.assert_not_called()
        mock_email_task.assert_called_once_with(self.users_ids, self.email_template, {})

    @patch('exchange.socialtrade.notify.task_send_mass_emails.delay')
    @patch('exchange.socialtrade.notify.task_send_mass_notifications.delay')
    @patch('exchange.socialtrade.notify.task_send_mass_sms.delay')
    def test_notify_with_notif_and_email_with_data(self, mock_sms_task, mock_notification_task, mock_email_task):
        notify_mass_users(
            users_ids=self.users_ids,
            sms_tps=None,
            sms_templates=self.sms_template,
            sms_texts=self.sms_text,
            notification_messages=self.notification_message,
            email_templates=self.email_template,
            email_data=None,
        )
        mock_sms_task.assert_not_called()
        mock_notification_task.assert_called_once_with(self.users_ids, self.notification_message)
        mock_email_task.assert_called_once_with(self.users_ids, self.email_template, None)
