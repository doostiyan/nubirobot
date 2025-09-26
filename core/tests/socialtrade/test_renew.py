from datetime import timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from unittest.mock import call, patch

import pytest
from django.conf import settings
from django.test import TestCase, override_settings

from exchange.accounts.models import Notification
from exchange.base.calendar import ir_now
from exchange.base.helpers import get_symbol_from_currency_code
from exchange.base.models import AMOUNT_PRECISIONS, RIAL, Settings
from exchange.socialtrade.crons import RenewSubscriptionsCron
from exchange.socialtrade.models import SocialTradeSubscription
from exchange.socialtrade.tasks import task_renew_subscription
from tests.socialtrade.helpers import SocialTradeMixin, enable_email


@patch('exchange.socialtrade.crons.task_renew_subscription')
class SendRenewalCronTest(SocialTradeMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        vp = self.user.get_verification_profile()
        vp.mobile_confirmed = True
        vp.email_confirmed = True
        vp.save()

        self.charge_wallet(self.user, RIAL, 10**10)

        self.candid_subscription1 = self.create_subscription(user=self.user, is_trial=False)
        self.candid_subscription1.expires_at = ir_now() + timedelta(minutes=4, seconds=59)
        self.candid_subscription1.save()
        self.candid_subscription1.leader.refresh_from_db()

        self.candid_subscription2 = self.create_subscription(user=self.user, is_trial=False)
        self.candid_subscription2.expires_at = ir_now() - timedelta(minutes=4, seconds=59)
        self.candid_subscription2.save()

        self.candid_subscription3 = self.create_subscription(user=self.user, is_trial=True)
        self.candid_subscription3.expires_at = ir_now() - timedelta(minutes=4, seconds=59)
        self.candid_subscription3.save()

        self.subscription_with_old_expire_date = self.create_subscription(user=self.user)
        self.subscription_with_old_expire_date.expires_at = ir_now() + timedelta(minutes=5, seconds=1)
        self.subscription_with_old_expire_date.save()

        self.not_candid_subscription2 = self.create_subscription(user=self.user)
        self.not_candid_subscription2.expires_at = ir_now() - timedelta(minutes=5, seconds=1)
        self.not_candid_subscription2.save()

        self.subscription_without_auto_renewal = self.create_subscription(
            user=self.user, is_trial=False, is_auto_renewal_enabled=False
        )
        self.subscription_without_auto_renewal.expires_at = ir_now() - timedelta(minutes=4, seconds=59)
        self.subscription_without_auto_renewal.save()

        self.subscription_with_deleted_leader = self.create_subscription(
            user=self.user, is_trial=False, is_auto_renewal_enabled=False
        )
        self.subscription_with_deleted_leader.expires_at = ir_now() - timedelta(minutes=4, seconds=59)
        self.subscription_with_deleted_leader.save()
        self.subscription_with_deleted_leader.leader.deleted_at = ir_now()
        self.subscription_with_deleted_leader.leader.save()

    def test_renewal_cron_query(self, renew_mock):
        RenewSubscriptionsCron().run()
        assert renew_mock.call_count == 3
        assert (
            renew_mock.call_args_list.sort()
            == [
                call((self.candid_subscription1.id,)),
                call((self.candid_subscription2.id,)),
                call((self.candid_subscription3.id,)),
            ].sort()
        )


class SendRenewalTaskTest(SocialTradeMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        vp = self.user.get_verification_profile()
        vp.mobile_confirmed = True
        vp.email_confirmed = True
        vp.save()

        self.user_wallet = self.charge_wallet(self.user, RIAL, Decimal(10**8))

        self.candid_subscription1 = self.create_subscription(user=self.user, is_trial=False, is_notif_enabled=False)
        self.candid_subscription1.expires_at = ir_now() + timedelta(minutes=4, seconds=59)
        self.candid_subscription1.save()
        self.candid_subscription1.leader.refresh_from_db()

        self.subscription_with_deleted_leader = self.create_subscription(
            user=self.user,
            is_trial=False,
            is_auto_renewal_enabled=False,
        )
        self.subscription_with_deleted_leader.expires_at = ir_now() - timedelta(minutes=4, seconds=59)
        self.subscription_with_deleted_leader.save()
        self.subscription_with_deleted_leader.leader.deleted_at = ir_now()
        self.subscription_with_deleted_leader.leader.save()
        self.user_wallet.refresh_from_db()

        Notification.objects.all().delete()

    def assert_renewed(self, subscription: SocialTradeSubscription):
        subscription.refresh_from_db()

        assert subscription.is_renewed
        renewed_subscription = SocialTradeSubscription.objects.filter(starts_at=subscription.expires_at).first()
        assert renewed_subscription
        assert renewed_subscription.starts_at == subscription.expires_at
        assert renewed_subscription.expires_at == subscription.expires_at + timedelta(
            days=settings.SOCIAL_TRADE['subscriptionPeriod'],
        )
        assert renewed_subscription.is_renewed is None
        assert renewed_subscription.canceled_at is None
        assert renewed_subscription.is_auto_renewal_enabled == subscription.is_auto_renewal_enabled
        assert renewed_subscription.is_notif_enabled == subscription.is_notif_enabled
        assert renewed_subscription.fee_amount == subscription.leader.subscription_fee
        assert renewed_subscription.fee_currency == subscription.leader.subscription_currency
        assert renewed_subscription.withdraw_transaction.amount == -subscription.leader.subscription_fee
        assert renewed_subscription.withdraw_transaction.currency == subscription.leader.subscription_currency

        symbol = get_symbol_from_currency_code(renewed_subscription.fee_currency).upper()
        precision = AMOUNT_PRECISIONS[f'{symbol}IRT'] if renewed_subscription.fee_currency != RIAL else 1
        assert renewed_subscription.leader_transaction.amount == (
            subscription.leader.subscription_fee * (1 - renewed_subscription.leader.system_fee_rate)
        ).quantize(precision, ROUND_HALF_EVEN)

        assert renewed_subscription.leader_transaction.currency == subscription.leader.subscription_currency
        assert renewed_subscription.system_transaction.amount == (
            subscription.leader.subscription_fee * renewed_subscription.leader.system_fee_rate
        ).quantize(precision, ROUND_HALF_EVEN)
        assert renewed_subscription.system_transaction.currency == subscription.leader.subscription_currency

        before_wallet_balance = self.user_wallet.balance
        self.user_wallet.refresh_from_db()
        assert self.user_wallet.balance == before_wallet_balance - subscription.leader.subscription_fee

    def assert_not_renewed(self, subscription: SocialTradeSubscription):
        subscription.refresh_from_db()

        assert subscription.is_renewed is False
        assert not SocialTradeSubscription.objects.filter(starts_at=subscription.expires_at).exists()

        before_wallet_balance = self.user_wallet.balance
        self.user_wallet.refresh_from_db()
        assert self.user_wallet.balance == before_wallet_balance

    def test_renewal_task(self):
        task_renew_subscription(self.candid_subscription1.id)
        self.assert_renewed(self.candid_subscription1)

    def test_renewal_task_fail_subscription_with_deleted_leader(self):
        self.user_wallet.refresh_from_db()
        task_renew_subscription(self.subscription_with_deleted_leader.id)
        self.assert_not_renewed(self.subscription_with_deleted_leader)

    def test_renewal_task_fail_when_reached_limit(self):
        self.user_wallet.refresh_from_db()
        Settings.set('social_trade_max_subscription_count', 0)

        task_renew_subscription(self.candid_subscription1.id)
        self.assert_not_renewed(self.candid_subscription1)

    def test_renewal_task_fail_when_insufficient_wallet_balance(self):
        self.user_wallet.balance = 0
        self.user_wallet.save()

        task_renew_subscription(self.candid_subscription1.id)
        self.assert_not_renewed(self.candid_subscription1)

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_renew_email_on_trial_success(self):
        self.candid_subscription1.is_trial = True
        self.candid_subscription1.save()

        with enable_email(self.user):
            task_renew_subscription(self.candid_subscription1.id)

    def test_renew_notif_on_trial_success(self):
        self.candid_subscription1.is_trial = True
        self.candid_subscription1.save()

        task_renew_subscription(self.candid_subscription1.id)
        notification = Notification.objects.filter(user=self.user).first()
        renewed_subscription = SocialTradeSubscription.objects.filter(
            starts_at=self.candid_subscription1.expires_at,
        ).first()

        assert notification
        assert notification.message == (
            f'کاربر گرامی، اشتراک سوشال ترید شما به مدت یک ماه فعال شده و هزینه اشتراک از کیف پول شما کسر شده است.\n'
            f'تریدر: {renewed_subscription.leader.nickname}\n'
            f'هزینه اشتراک: 100 تومان\n'
            f'تاریخ پایان اشتراک: {renewed_subscription.shamsi_expire_date}'
        )

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_renew_email_on_subscription_success(self):
        self.candid_subscription1.is_trial = False
        self.candid_subscription1.save()

        with enable_email(self.user):
            task_renew_subscription(self.candid_subscription1.id)

    def test_renew_notif_on_subscription_success(self):
        self.candid_subscription1.is_trial = False
        self.candid_subscription1.save()

        task_renew_subscription(self.candid_subscription1.id)
        notification = Notification.objects.filter(user=self.user).first()
        renewed_subscription = SocialTradeSubscription.objects.filter(
            starts_at=self.candid_subscription1.expires_at,
        ).first()

        assert notification
        assert notification.message == (
            f'کاربر گرامی، اشتراک سوشال ترید شما به مدت یک ماه تمدید شده و هزینه اشتراک از کیف پول شما کسر شده است.\n'
            f'تریدر: {renewed_subscription.leader.nickname}\n'
            f'هزینه اشتراک: 100 تومان\n'
            f'تاریخ پایان اشتراک: {renewed_subscription.shamsi_expire_date}'
        )

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_renew_email_on_trial_fail_insufficient_balance(self):
        self.candid_subscription1.is_trial = True
        self.candid_subscription1.save()
        self.user_wallet.balance = 0
        self.user_wallet.save()

        with enable_email(self.user):
            task_renew_subscription(self.candid_subscription1.id)

    def test_renew_notif_on_trial_fail_insufficient_balance(self):
        self.candid_subscription1.is_trial = True
        self.candid_subscription1.save()
        self.user_wallet.balance = 0
        self.user_wallet.save()

        task_renew_subscription(self.candid_subscription1.id)
        notification = Notification.objects.filter(user=self.user).first()

        assert notification
        assert notification.message == (
            f'کاربر گرامی، موجودی شما برای فعالسازی اشتراک سوشال ترید، کافی نمی‌باشد. '
            f'برای افزایش موجودی و فعال‌سازی اشتراک به پنل کاربری مراجعه نمایید.\n'
            f'تریدر: {self.candid_subscription1.leader.nickname}\n'
            f'هزینه اشتراک: 100 تومان'
        )

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_renew_email_on_subscription_fail_insufficient_balance(self):
        self.candid_subscription1.is_trial = False
        self.candid_subscription1.save()
        self.user_wallet.balance = 0
        self.user_wallet.save()

        with enable_email(self.user):
            task_renew_subscription(self.candid_subscription1.id)

    def test_renew_notif_on_subscription_fail_insufficient_balance(self):
        self.candid_subscription1.is_trial = False
        self.candid_subscription1.save()
        self.user_wallet.balance = 0
        self.user_wallet.save()

        task_renew_subscription(self.candid_subscription1.id)
        notification = Notification.objects.filter(user=self.user).first()

        assert notification
        assert notification.message == (
            f'کاربر گرامی، موجودی شما برای تمدید اشتراک سوشال ترید، کافی نمی‌باشد. '
            f'لطفا با مراجعه به پنل کاربری موجودی کیف پول خود را افزایش داده و سپس اقدام به فعالسازی اشتراک نمایید.\n'
            f'تریدر: {self.candid_subscription1.leader.nickname}\n'
            f'هزینه اشتراک: 100 تومان'
        )
