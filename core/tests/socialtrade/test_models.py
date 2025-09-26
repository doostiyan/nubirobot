from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase, override_settings

from exchange.accounts.models import Notification, User, UserSms
from exchange.base.calendar import ir_now
from exchange.base.models import ACTIVE_CURRENCIES, Currencies
from exchange.base.serializers import serialize
from exchange.socialtrade.models import Leader, LeadershipRequest, SocialTradeSubscription
from exchange.socialtrade.tasks import task_send_email, task_send_mass_emails
from exchange.wallet.models import Wallet
from tests.socialtrade.helpers import SocialTradeMixin, SocialTradeTestDataMixin, enable_email


class LeadershipRequestTest(SocialTradeMixin, TestCase):
    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)
        self.user.mobile = '09012345678'
        self.user.save()
        vp = self.user.get_verification_profile()
        vp.mobile_confirmed = True
        vp.email_confirmed = True
        vp.save()

        self.nickname = 'BestLeader'
        self.subscription_fee = Decimal(5)
        self.subscription_currency = Currencies.usdt

        self.leadership_request = LeadershipRequest.objects.create(
            user=self.user,
            nickname=self.nickname,
            avatar=self.create_avatar(),
            subscription_fee=self.subscription_fee,
            subscription_currency=self.subscription_currency,
        )
        Notification.objects.all().delete()

    @patch('exchange.socialtrade.notify.EmailManager.send_email')
    def test_accept(self, send_email_mock):
        self.leadership_request.accept(Decimal('12.34'))
        leader = Leader.objects.filter(
            user=self.user,
            nickname=self.nickname,
            subscription_fee=self.subscription_fee,
            subscription_currency=self.subscription_currency,
        ).first()
        assert leader
        assert leader.user == self.leadership_request.user
        assert leader.system_fee_percentage == Decimal('12.34')
        assert leader.system_fee_rate == Decimal('0.1234')
        assert (
            UserSms.objects.filter(
                user=self.user,
                tp=UserSms.TYPES.social_trade_leadership_acceptance,
                template=UserSms.TEMPLATES.social_trade_leadership_acceptance,
            ).count()
            == 1
        )
        assert Notification.objects.filter(user=self.user).count() == 1
        assert send_email_mock.call_count == 1

    @patch('exchange.socialtrade.notify.EmailManager.send_email')
    def test_accept_when_deleted_before(self, send_email_mock):
        self.leadership_request.accept(Decimal('12.345'))

        leader = Leader.objects.filter(
            user=self.user,
            nickname=self.nickname,
            subscription_fee=self.subscription_fee,
            subscription_currency=self.subscription_currency,
        ).first()

        assert leader

        leader.delete_leader(1)
        leadership_request = LeadershipRequest.objects.create(
            user=self.user,
            nickname='new-nickname',
            avatar=self.create_avatar(),
            subscription_fee='10.43',
            subscription_currency=Currencies.usdt,
        )
        leadership_request.accept(10)
        leader.refresh_from_db()

        assert leader.system_fee_percentage == Decimal('10')
        assert leader.system_fee_rate == Decimal('0.1')
        assert leader.nickname == 'new-nickname'
        assert leader.subscription_fee == Decimal('10.43')
        assert leader.subscription_currency == Currencies.usdt
        assert leader.deleted_at is None
        assert leader.delete_reason is None
        assert (
            UserSms.objects.filter(
                user=self.user,
                tp=UserSms.TYPES.social_trade_leadership_acceptance,
                template=UserSms.TEMPLATES.social_trade_leadership_acceptance,
            ).count()
            == 2
        )
        assert Notification.objects.filter(user=self.user).count() == 3
        assert send_email_mock.call_count == 3

    @patch('exchange.socialtrade.notify.EmailManager.send_email')
    def test_reject(self, send_email_mock):
        self.leadership_request.reject(reason=LeadershipRequest.REASONS.low_experience)
        assert Leader.objects.filter(user=self.user).count() == 0
        assert UserSms.objects.filter(
            user=self.user, tp=UserSms.TYPES.social_trade_leadership_rejection,
            template=UserSms.TEMPLATES.social_trade_leadership_rejection
        ).count() == 1
        assert Notification.objects.filter(user=self.user).count() == 1
        assert send_email_mock.call_count == 1

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_accept_request_call_email(self):
        with enable_email(self.user):
            self.leadership_request.accept(10)

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_reject_request_because_of_low_experience_call_email(self):
        with enable_email(self.user):
            self.leadership_request.reject(LeadershipRequest.REASONS.low_experience)

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_reject_request_because_of_low_trade_volume_call_email(self):
        with enable_email(self.user):
            self.leadership_request.reject(LeadershipRequest.REASONS.low_trade_volume)

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_reject_request_because_of_no_new_registration_call_email(self):
        with enable_email(self.user):
            self.leadership_request.reject(LeadershipRequest.REASONS.no_new_registration)

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_reject_request_because_of_invalid_nickname_call_email(self):
        with enable_email(self.user):
            self.leadership_request.reject(LeadershipRequest.REASONS.invalid_nickname)

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_reject_request_because_of_invalid_avatar_call_email(self):
        with enable_email(self.user):
            self.leadership_request.reject(LeadershipRequest.REASONS.invalid_avatar)


class LeaderModelTest(SocialTradeTestDataMixin, TestCase):
    def setUp(self) -> None:
        super().create_test_data()
        super().setUp()

    @patch('exchange.socialtrade.models.Leader._notify_leader_deletion_to_trials')
    @patch('exchange.socialtrade.models.Leader._notify_leader_deletion_to_subscribers')
    @patch('exchange.socialtrade.models.Leader._notify_leader_deletion_to_leader')
    @patch('exchange.socialtrade.models.SocialTradeSubscription.end_subscriptions_of_a_leader')
    def test_delete_leader(
        self,
        mock_end_subscriptions,
        mock_notify_leader_deletion_to_leader,
        mock_notify_leader_deletion_to_subscribers,
        mock_notify_leader_deletion_to_trials,
    ):
        # Should call 3 different methods to notify the leader, the subscribers, and trial followers
        self.leader.delete_leader(1)
        assert self.leader.deleted_at is not None
        assert self.leader.delete_reason == 1
        mock_notify_leader_deletion_to_leader.assert_called_once()
        mock_notify_leader_deletion_to_subscribers.assert_called_once()
        mock_notify_leader_deletion_to_trials.assert_called_once()
        mock_end_subscriptions.assert_called_once_with(self.leader)

    @patch('exchange.socialtrade.notifs.notify_user')
    def test_notify_leader_deletion_to_leader(self, mock_notify_user):
        # Should send the proper sms, notif, and email to the leader when the leader is deleted
        self.leader.delete_reason = Leader.DELETE_REASONS.leader_request
        self.leader.save()
        self.leader._notify_leader_deletion_to_leader()
        mock_notify_user.assert_called_once_with(
            user=self.leader.user,
            sms_tp=UserSms.TYPES.social_trade_notify_leader_of_deletion,
            sms_template=UserSms.TEMPLATES.social_trade_notify_leader_of_deletion,
            sms_text=self.leader.get_delete_reason_display(),
            notification_message=(
                f'کاربر گرامی،‌ از این تاریخ شما امکان دریافت اشتراک جدید را نداشته و '
                f'پس از پایان دوره اشتراک کاربران، امکان فعالیت به عنوان تریدر سوشال ترید'
                f' را نخواهید داشت. دلیل: {self.leader.get_delete_reason_display()}'
            ),
            email_template='socialtrade/leader_deletion_leader',
            email_data={
                'sms_text': self.leader.get_delete_reason_display(),
                'reason': self.leader.get_delete_reason_display(),
                'email_title': 'اطلاع رسانی سوشال ترید: عدم امکان فعالیت به عنوان تریدر',
            },
        )

    @patch('exchange.socialtrade.notifs.notify_mass_users')
    def test_notify_leader_deletion_to_subscribers(self, mock_notify_mass_users):
        # Should send the proper sms, notif, and email to the subscribers when the leader is deleted
        user_ids_we_should_notify = [
            subscription.subscriber.id for subscription in self.subscriptions if subscription.is_active
        ]
        self.leader._notify_leader_deletion_to_subscribers()
        mock_notify_mass_users.assert_called_once_with(
            users_ids=user_ids_we_should_notify,
            sms_tps=UserSms.TYPES.social_trade_notify_subscribers_of_leader_deletion,
            sms_templates=UserSms.TEMPLATES.social_trade_notify_subscribers_of_leader_deletion,
            sms_texts=self.leader.nickname,
            notification_messages=(
                f'کاربر گرامی، تریدر انتخابی شما تا پایان دوره فعلی اشتراک فعالیت خواهد داشت'
                f' و پس از آن امکان تمدید اشتراک وجود نخواهد داشت.\nتریدر: {self.leader.nickname}'
            ),
            email_templates='socialtrade/leader_deletion_subscribers',
            email_data={
                'sms_text': self.leader.nickname,
                'nickname': self.leader.nickname,
                'email_title': 'اطلاع رسانی سوشال ترید: عدم فعالیت تریدر انتخابی',
            },
        )

    @patch('exchange.socialtrade.notifs.notify_mass_users')
    def test_notify_leader_deletion_to_trials(self, mock_notify_mass_users):
        # Should send the proper sms, notif, and email to the trial followers when the leader is deleted
        user_ids_we_should_notify = [trial.subscriber.id for trial in self.trials if trial.is_active]
        self.leader._notify_leader_deletion_to_trials()
        mock_notify_mass_users.assert_called_once_with(
            users_ids=user_ids_we_should_notify,
            sms_tps=UserSms.TYPES.social_trade_notify_trials_of_leader_deletion,
            sms_templates=UserSms.TEMPLATES.social_trade_notify_trials_of_leader_deletion,
            sms_texts=self.leader.nickname,
            notification_messages=(
                f'کاربر گرامی، به دلیل عدم فعالیت تریدر انتخابی شما، امکان فعال‌سازی اشتراک سوشال ترید'
                f' برای تریدر انتخابی وجود نداشته و دوره آزمایشی اشتراک شما به پایان رسیده است.'
                f'\nتریدر: {self.leader.nickname}'
            ),
            email_templates='socialtrade/leader_deletion_trials',
            email_data={
                'sms_text': self.leader.nickname,
                'nickname': self.leader.nickname,
                'email_title': 'اطلاع رسانی سوشال ترید: عدم فعالیت تریدر انتخابی',
            },
        )

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_notify_leader_of_leader_deletion_emails_with_self_request_reason(self):
        with enable_email(self.leader.user):
            self.leader.delete_leader(reason=Leader.DELETE_REASONS.leader_request)

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_notify_leader_of_leader_deletion_emails_with_low_trade_reason(self):
        with enable_email(self.leader.user):
            self.leader.delete_leader(reason=Leader.DELETE_REASONS.low_trade)

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_notify_leader_of_leader_deletion_emails_with_ineligibility_reason(self):
        with enable_email(self.leader.user):
            self.leader.delete_leader(reason=Leader.DELETE_REASONS.ineligibility)

    @pytest.mark.slow()
    @patch.object(task_send_mass_emails, 'delay', task_send_mass_emails)
    @patch.object(task_send_email, 'delay', task_send_email)
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_notify_all_followers_of_leader_deletion_emails_with_ineligibility_reason(self):
        with enable_email(self.subscribers):
            self.leader.delete_leader(reason=Leader.DELETE_REASONS.ineligibility)

    def test_get_subscribed_leaders_for_subscribers(self):
        # Should return the two leaders the subscribers subscribe, both on paid subscription and on trial
        leaders = list(Leader.get_subscribed_to(self.subscribers[0]))
        leaders.sort(key=lambda leader: leader.id)
        assert leaders == self.leaders

        leaders = list(Leader.get_subscribed_to(self.subscribers[4]))
        leaders.sort(key=lambda leader: leader.id)
        assert leaders == self.leaders

    def test_get_subscribed_leaders_for_non_subscribers(self):
        # Should return no leaders for users with expired, cancelled, or waiting subscriptions
        leaders = list(Leader.get_subscribed_to(self.subscribers[1]))
        assert leaders == []

        leaders = list(Leader.get_subscribed_to(self.subscribers[2]))
        assert leaders == []

        leaders = list(Leader.get_subscribed_to(self.subscribers[3]))
        assert leaders == []

    def test_number_of_subscribers(self):
        # Calling the annotation on multiple leaders
        leaders = list(Leader.objects.all().annotate_number_of_subscribers())
        leaders.sort(key=lambda l: l.id)
        assert leaders[0].number_of_subscribers == 2
        assert leaders[1].number_of_subscribers == 2
        assert leaders[2].number_of_subscribers == 0

        # A subscription expiring should reduce the number of leader's subscribers by 1
        self.subscriptions[0].expires_at = ir_now() - timedelta(hours=1)
        self.subscriptions[0].save()
        leader = list(Leader.objects.filter(pk=self.leader.id).annotate_number_of_subscribers())[0]
        assert leader.number_of_subscribers == 1

        # Cancelling a subscription should reduce the number of leader's subscribers by 1
        self.trials[0].canceled_at = ir_now()
        self.trials[0].save()
        leader = list(Leader.objects.filter(pk=self.leader.id).annotate_number_of_subscribers())[0]
        assert leader.number_of_subscribers == 0

    def test_number_of_unsubscribes(self):
        # This leader has 1 expired subscription , 1 canceled subscription, 1 expired trial of another user, and
        #  1 canceled trial
        leader = list(Leader.objects.filter(pk=self.leader.id).annotate_number_of_unsubscribes())[0]
        assert leader.number_of_unsubscribes == 4

        # Adding a canceled trial before a canceled subscription should not increase the number of unsubscribes
        self.charge_user_wallet(self.subscribers[2], Currencies.usdt, Decimal('100'))
        SocialTradeSubscription.objects.create(
            leader=self.leader,
            subscriber=self.subscribers[2],
            is_trial=False,
            starts_at=ir_now() - timedelta(days=2),
            expires_at=ir_now() + timedelta(days=2),
            canceled_at=ir_now() - timedelta(days=1, hours=23),
            fee_amount=self.leader.subscription_fee,
            fee_currency=self.leader.subscription_currency,
        )
        leader = list(Leader.objects.filter(pk=self.leader.id).annotate_number_of_unsubscribes())[0]
        assert leader.number_of_unsubscribes == 4

        # Removing one canceled subscription should decrease the number of unsubscribes by 1
        self.subscriptions[2].canceled_at = None
        self.subscriptions[2].save()
        leaders = list(Leader.objects.all().annotate_number_of_unsubscribes())
        leaders.sort(key=lambda l: l.id)
        assert leaders[0].number_of_unsubscribes == 3
        assert leaders[1].number_of_unsubscribes == 4
        assert leaders[2].number_of_unsubscribes == 0

        # Creating a subscription after a canceled trial should decrease the number of unsubscribes by 1
        subscriber_wallet = Wallet.get_user_wallet(self.trials[2].subscriber, self.leader.subscription_currency)
        subscriber_wallet.create_transaction(
            tp='social_trade',
            amount=self.leader.subscription_fee,
            description=f'تست',
        ).commit()
        SocialTradeSubscription.objects.create(
            leader=self.leader,
            subscriber=self.trials[2].subscriber,
            starts_at=ir_now(),
            expires_at=ir_now() + timedelta(days=2),
            is_trial=False,
        )
        leader = list(Leader.objects.filter(pk=self.leader.id).annotate_number_of_unsubscribes())[0]
        assert leader.number_of_unsubscribes == 2

        # Removing an expired subscription should decrease the number of unsubscribes by 1
        self.subscriptions[1].expires_at = ir_now() + timedelta(days=2)
        self.subscriptions[1].save()
        leader = list(Leader.objects.filter(pk=self.leader.id).annotate_number_of_unsubscribes())[0]
        assert leader.number_of_unsubscribes == 1

        # Creating a subscription after an expired trial should decrease the number of unsubscribes by 1
        subscriber_wallet = Wallet.get_user_wallet(self.trials[1].subscriber, self.leader.subscription_currency)
        subscriber_wallet.create_transaction(
            tp='social_trade',
            amount=self.leader.subscription_fee,
            description=f'تست',
        ).commit()
        SocialTradeSubscription.objects.create(
            leader=self.leader,
            subscriber=self.trials[1].subscriber,
            starts_at=ir_now(),
            expires_at=ir_now() + timedelta(days=2),
            is_trial=False,
        )
        leader = list(Leader.objects.filter(pk=self.leader.id).annotate_number_of_unsubscribes())[0]
        assert leader.number_of_unsubscribes == 0

    def test_leader_total_daily_portfo_without_withdraws_and_deposits(self):
        self._create_leader_portfolios_without_withdraw_and_deposit(self.leader, self.leader_two)
        leaders = list(Leader.objects.all())
        leaders.sort(key=lambda leader: leader.id)
        for leader in leaders:
            if leader.id == self.leader.id:
                assert leader.daily_profits == [
                    dict(
                        report_date=serialize(self.report_dates[0]),
                        profit_percentage='0',
                        cumulative_profit_percentage='0',
                    ),
                    dict(
                        report_date=serialize(self.report_dates[1]),
                        profit_percentage='50',
                        cumulative_profit_percentage='50',
                    ),
                    dict(
                        report_date=serialize(self.report_dates[2]),
                        profit_percentage='-20',
                        cumulative_profit_percentage='20',
                    ),
                    dict(
                        report_date=serialize(self.report_dates[3]),
                        profit_percentage='50',
                        cumulative_profit_percentage='80',
                    ),
                ]
            elif leader.id == self.leader_two.id:
                assert leader.daily_profits == [
                    dict(
                        report_date=serialize(self.report_dates[2]),
                        profit_percentage='0',
                        cumulative_profit_percentage='0',
                    ),
                    dict(
                        report_date=serialize(self.report_dates[3]),
                        profit_percentage='50',
                        cumulative_profit_percentage='50',
                    ),
                ]
            else:
                assert leader.daily_profits == []

    def test_leader_total_daily_portfo_with_withdraws_and_deposits(self):
        self._create_leader_portfolios_with_withdraw_and_deposit(self.leader, self.leader_two)
        leaders = list(Leader.objects.all())
        leaders.sort(key=lambda leader: leader.id)
        for leader in leaders:
            if leader.id == self.leader.id:
                assert leader.daily_profits == [
                    dict(
                        report_date=serialize(self.report_dates[0]),
                        profit_percentage='0',
                        cumulative_profit_percentage='0',
                    ),
                    dict(
                        report_date=serialize(self.report_dates[1]),
                        profit_percentage='40',
                        cumulative_profit_percentage='33.33',
                    ),
                    dict(
                        report_date=serialize(self.report_dates[2]),
                        profit_percentage='20',
                        cumulative_profit_percentage='43.75',
                    ),
                    dict(
                        report_date=serialize(self.report_dates[3]),
                        profit_percentage='-14.29',
                        cumulative_profit_percentage='33.33',
                    ),
                ]
            elif leader.id == self.leader_two.id:
                assert leader.daily_profits == [
                    dict(
                        report_date=serialize(self.report_dates[2]),
                        profit_percentage='0',
                        cumulative_profit_percentage='0',
                    ),
                    dict(
                        report_date=serialize(self.report_dates[3]),
                        profit_percentage='40',
                        cumulative_profit_percentage='33.33',
                    ),
                ]

    @patch('exchange.wallet.estimator.PriceEstimator.get_price_range', new_callable=MagicMock)
    def test_get_asset_ratios(self, mock_price_estimator):
        currencies_real_value = {
            Currencies.rls: (1, 1),
            Currencies.usdt: (50_000_0, 49_000_0),
            Currencies.btc: (1_000_000_000_0, 999_900_000_0),
        }

        def get_price_range(currency: int, *_, db_fallback=False, **__) -> tuple:
            return currencies_real_value.get(currency, (0, 0))

        mock_price_estimator.side_effect = get_price_range

        # Zero assets case:
        self.create_user_wallets(self.leader.user)
        self.charge_user_wallet(self.leader.user, Currencies.usdt, Decimal(0))
        leader_assets = self.leader.asset_ratios
        for currency in ACTIVE_CURRENCIES:
            assert currency in leader_assets.keys()
            assert leader_assets[currency] == Decimal(0.0)

        self.charge_user_wallet(self.leader.user, Currencies.rls, Decimal(50_000_0))
        self.charge_user_wallet(self.leader.user, Currencies.usdt, Decimal(3))

        leader_assets = self.leader.asset_ratios
        for currency in ACTIVE_CURRENCIES:
            assert currency in leader_assets.keys()
            if currency == Currencies.rls:
                assert leader_assets[currency] == Decimal(0.25)
            elif currency == Currencies.usdt:
                assert leader_assets[currency] == Decimal(0.75)
            else:
                assert leader_assets[currency] == Decimal(0)

        self.charge_user_wallet(self.leader.user, Currencies.btc, Decimal(0.0198))
        leader_assets = self.leader.asset_ratios
        for currency in ACTIVE_CURRENCIES:
            assert currency in leader_assets.keys()
            if currency == Currencies.rls:
                assert leader_assets[currency] == Decimal('0.002500')
            elif currency == Currencies.usdt:
                assert leader_assets[currency] == Decimal('0.007500')
            elif currency == Currencies.btc:
                assert leader_assets[currency] == Decimal('0.990000')
            else:
                assert leader_assets[currency] == Decimal(0)


class SocialTradeSubscriptionTest(SocialTradeTestDataMixin, TestCase):
    def setUp(self) -> None:
        super().create_test_data()
        super().setUp()

    def test_end_subscriptions_of_a_leader(self):
        # There are a total of 8 subscriptions to self.leader:
        # 4 on trial (1 active, 1 waiting, 1 expired, and 1 canceled).
        # 4 on paid subscriptions (1 active, 1 waiting, 1 expired, and 1 canceled).
        # Deleting self.leader should cancel the active trial and turn off auto_renewal of the active subscription
        SocialTradeSubscription.get_actives().update(is_auto_renewal_enabled=True)
        SocialTradeSubscription.end_subscriptions_of_a_leader(self.leader)
        assert SocialTradeSubscription.get_actives().filter(leader=self.leader, is_trial=False).count() == 1
        assert SocialTradeSubscription.get_actives().filter(leader=self.leader, is_trial=True).count() == 0
        assert (
            SocialTradeSubscription.get_actives().filter(leader=self.leader, is_auto_renewal_enabled=True).count() == 0
        )
