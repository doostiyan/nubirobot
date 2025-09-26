from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import TestCase, override_settings

from exchange.accounts.models import Notification, User
from exchange.base.models import Currencies, Settings
from exchange.staking.models import ExternalEarningPlatform, Plan, PlanTransaction, StakingTransaction
from exchange.staking.signals import get_notif_func

from .utils import PlanArgsMixin


class UserStakingNotificationTests(TestCase):
    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_email_notif(self):
        user = User.objects.first()
        plan = Plan.objects.create(
            **PlanArgsMixin.get_plan_kwargs(
                ExternalEarningPlatform.objects.create(
                    tp=ExternalEarningPlatform.TYPES.staking,
                    currency=Currencies.btc,
                    network='network',
                    address='address',
                    tag='tag',
                )
            )
        )
        assert user is not None
        assert plan is not None
        call_command('update_email_templates')
        Settings.set_dict('email_whitelist', [user.email])
        Settings.set('send_staking_email_notification', 'yes')
        get_notif_func(
            StakingTransaction.objects.create(
                user_id=user.id,
                plan_id=plan.id,
                tp=StakingTransaction.TYPES.instant_end_request,
                amount=Decimal('11'),
            )
        )()
        StakingTransaction.objects.create(
            user_id=user.id,
            plan_id=plan.id,
            tp=StakingTransaction.TYPES.stake,
            amount=Decimal('11'),
        )
        reward_trx_no_extend = StakingTransaction.objects.create(
            user_id=user.id,
            plan_id=plan.id,
            tp=StakingTransaction.TYPES.give_reward,
            amount=Decimal('11'),
        )
        get_notif_func(reward_trx_no_extend)()
        StakingTransaction.objects.create(
            user_id=user.id,
            plan_id=plan.id,
            tp=StakingTransaction.TYPES.extend_out,
            amount=Decimal('11'),
        )
        reward_trx_no_extend.delete()
        get_notif_func(
            StakingTransaction.objects.create(
                user_id=user.id,
                plan_id=plan.id,
                tp=StakingTransaction.TYPES.give_reward,
                amount=Decimal('11'),
            )
        )()
        with patch('django.db.connection.close'):
            call_command('send_queued_mail')

    def test_send_notif_on_give_reward_transaction_will_round_realized_apr(self):
        user = User.objects.first()
        plan = Plan.objects.create(
            **PlanArgsMixin.get_plan_kwargs(
                ExternalEarningPlatform.objects.create(
                    tp=ExternalEarningPlatform.TYPES.staking,
                    currency=Currencies.btc,
                    network='network',
                    address='address',
                    tag='tag',
                )
            )
        )
        assert user is not None
        assert plan is not None

        plan.transactions.create(
            tp=PlanTransaction.TYPES.give_reward,
            amount=Decimal('29.33456799989'),
            parent=plan.transactions.create(
                tp=PlanTransaction.TYPES.announce_reward,
                amount=Decimal('29.33456799989'),
            ),
        )
        StakingTransaction.objects.create(
            user_id=user.id,
            plan_id=plan.id,
            tp=StakingTransaction.TYPES.stake,
            amount=Decimal('11'),
        )
        reward_trx_no_extend = StakingTransaction.objects.create(
            user_id=user.id,
            plan_id=plan.id,
            tp=StakingTransaction.TYPES.give_reward,
            amount=Decimal('110.1455678'),
        )

        get_notif_func(reward_trx_no_extend)()

        notif = Notification.objects.filter(user=user, message__contains='(APR)').first()
        assert str(round(plan.realized_apr, 2)) in notif.message

    def test_send_notif_on_give_reward_when_user_has_extend_out_transaction(self):
        user = User.objects.first()
        plan = Plan.objects.create(
            **PlanArgsMixin.get_plan_kwargs(
                ExternalEarningPlatform.objects.create(
                    tp=ExternalEarningPlatform.TYPES.staking,
                    currency=Currencies.btc,
                    network='network',
                    address='address',
                    tag='tag',
                )
            )
        )
        plan.transactions.create(
            tp=PlanTransaction.TYPES.give_reward,
            amount=Decimal('1.3345'),
            parent=plan.transactions.create(
                tp=PlanTransaction.TYPES.announce_reward,
                amount=Decimal('0.5'),
            ),
        )
        StakingTransaction.objects.create(
            user_id=user.id,
            plan_id=plan.id,
            tp=StakingTransaction.TYPES.stake,
            amount=Decimal('11'),
        )
        StakingTransaction.objects.create(
            user_id=user.id,
            plan_id=plan.id,
            tp=StakingTransaction.TYPES.extend_out,
            amount=Decimal('11'),
        )
        transaction = StakingTransaction.objects.create(
            user_id=user.id,
            plan_id=plan.id,
            tp=StakingTransaction.TYPES.give_reward,
            amount=Decimal('0.1103'),
        )

        get_notif_func(transaction)()

        notif = Notification.objects.filter(user=user, message__contains='(APR)').first()
        assert (
            notif.message
            == """مدت زمان طرح استیکینگ 1 روزه‌ی بیت‌کوین شما به پایان رسید و پاداش طرح با درصد بازده سالانه (APR) برابر 182.50 درصد به میزان 0.11 بیت‌کوین به کیف پول شما واریز شد. با توجه به فعال بودن تمدید خودکار طرح استیکینگ 1 روزه‌ی بیت‌کوین شما این طرح برای یک دوره‌ی دیگر فعال شد. جهت پیگیری وضعیت به پنل طرح استیکینگ 1 روزه‌ی بیت‌کوین خود مراجعه نمایید."""
        )

    def test_send_notif_on_give_reward_when_user_has_extend_out_transaction_with_zero_amount(self):
        user = User.objects.first()
        plan = Plan.objects.create(
            **PlanArgsMixin.get_plan_kwargs(
                ExternalEarningPlatform.objects.create(
                    tp=ExternalEarningPlatform.TYPES.staking,
                    currency=Currencies.btc,
                    network='network',
                    address='address',
                    tag='tag',
                )
            )
        )
        plan.transactions.create(
            tp=PlanTransaction.TYPES.give_reward,
            amount=Decimal('5.5'),
            parent=plan.transactions.create(
                tp=PlanTransaction.TYPES.announce_reward,
                amount=Decimal('3.3789'),
            ),
        )
        StakingTransaction.objects.create(
            user_id=user.id,
            plan_id=plan.id,
            tp=StakingTransaction.TYPES.stake,
            amount=Decimal('50'),
        )
        StakingTransaction.objects.create(
            user_id=user.id,
            plan_id=plan.id,
            tp=StakingTransaction.TYPES.extend_out,
            amount=0,
        )
        transaction = StakingTransaction.objects.create(
            user_id=user.id,
            plan_id=plan.id,
            tp=StakingTransaction.TYPES.give_reward,
            amount=Decimal('0.35001'),
        )

        get_notif_func(transaction)()

        notif = Notification.objects.filter(user=user, message__contains='(APR)').first()
        assert (
            notif.message
            == """مدت زمان طرح استیکینگ 1 روزه‌ی بیت‌کوین شما به پایان رسید و پاداش طرح با درصد بازده سالانه (APR) برابر 1233.30 درصد به میزان 0.35 بیت‌کوین به کیف پول شما واریز شد. جهت پیگیری وضعیت به پنل طرح استیکینگ 1 روزه‌ی بیت‌کوین خود مراجعه کنید."""
        )
