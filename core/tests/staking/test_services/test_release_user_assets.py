from datetime import timedelta
from decimal import Decimal

import freezegun
import pytest
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.staking.errors import InvalidPlanId
from exchange.staking.models import ExternalEarningPlatform, Plan, StakingTransaction
from exchange.staking.service.release_assets import _release_user_asset
from exchange.wallet.models import Transaction
from tests.staking.utils import StakingTestDataMixin


class ReleaseUserAssetsTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        # instant ends release time is evey day at 15 PM
        self.today_before_15_pm = ir_now().replace(hour=9, minute=30)
        self.today_15_pm = ir_now().replace(hour=15, minute=0)
        self.today_after_15_pm = ir_now().replace(hour=19, minute=30)

        self.plan1 = self.create_plan(**self.get_plan_kwargs())
        self.plan2 = self.create_plan(**self.get_plan_kwargs())
        self.plan2.unstaking_period = timedelta(days=10)
        self.plan2.save(update_fields=['unstaking_period'])
        self.user = self.create_user()

        # user instant end request in plan1
        self.instant_end_request = self.create_staking_transaction(
            user=self.user, plan=self.plan1, amount=Decimal('10'), tp=StakingTransaction.TYPES.instant_end_request
        )
        self.unstake_instant_end_request = self.create_staking_transaction(
            user=self.user,
            plan=self.plan1,
            amount=Decimal('10'),
            tp=StakingTransaction.TYPES.unstake,
            parent=self.instant_end_request,
            created_at=self.today_before_15_pm,
        )

        # user finished unstaking period in plan2 and can be released
        self.user_plan2_auto_end_transaction = self.create_staking_transaction(
            user=self.user, plan=self.plan2, amount=Decimal('0.0'), tp=StakingTransaction.TYPES.auto_end_request
        )
        self.plan2_unstake_transaction = self.create_staking_transaction(
            user=self.user,
            plan=self.plan2,
            amount=Decimal('110'),
            tp=StakingTransaction.TYPES.unstake,
            parent=self.user_plan2_auto_end_transaction,
            created_at=ir_now() - self.plan2.unstaking_period - timedelta(days=3),
        )

    def assert_success_release(
        self,
        unstake_transaction: StakingTransaction,
        user: User = None,
        plan: Plan = None,
        transaction_ref_module: int = 134,
        transaction_tp: int = 130,
    ):
        release_transaction = StakingTransaction.objects.get(
            user=user,
            plan=plan,
            tp=StakingTransaction.TYPES.release,
            amount=unstake_transaction.amount,
            parent=unstake_transaction,
        )
        assert Transaction.objects.get(
            ref_id=release_transaction.id,
            ref_module=transaction_ref_module,
            description=f'بازگشت دارایی {plan.fa_description}.',
            amount=unstake_transaction.amount,
            wallet__currency=plan.currency,
            wallet__user=user,
            tp=transaction_tp,
        )

    def test_success_release_when_user_stakings_are_after_unstaking_period(self):
        _release_user_asset(self.user.id, self.plan2.id)

        self.assert_success_release(self.plan2_unstake_transaction, user=self.user, plan=self.plan2)

    def test_success_release_when_user_yield_farmings_are_after_unstaking_period(self):
        plan = self.create_plan(
            **self.get_plan_kwargs(
                self.add_external_platform(currency=30, tp=ExternalEarningPlatform.TYPES.yield_aggregator)
            )
        )
        auto_end_transaction = self.create_staking_transaction(
            user=self.user, plan=self.plan2, amount=Decimal('0.0'), tp=StakingTransaction.TYPES.auto_end_request
        )
        plan_unstake_transaction = self.create_staking_transaction(
            user=self.user,
            plan=plan,
            amount=Decimal('40'),
            tp=StakingTransaction.TYPES.unstake,
            parent=auto_end_transaction,
            created_at=ir_now() - self.plan2.unstaking_period - timedelta(days=3),
        )

        _release_user_asset(self.user.id, plan.id)

        self.assert_success_release(
            plan_unstake_transaction,
            user=self.user,
            plan=plan,
            transaction_tp=160,
            transaction_ref_module=163,
        )

    def test_release_instant_end_request_successfully(self):
        with freezegun.freeze_time(self.today_after_15_pm):
            assert ir_now() == self.today_after_15_pm
            _release_user_asset(self.user.id, self.plan1.id)

        self.assert_success_release(self.unstake_instant_end_request, user=self.user, plan=self.plan1)

    def test_release_instant_end_requests_that_unstake_exactly_at_15_pm(self):
        self.unstake_instant_end_request.created_at = self.today_15_pm
        self.unstake_instant_end_request.save(update_fields=['created_at'])

        with freezegun.freeze_time(self.today_after_15_pm):
            assert ir_now() == self.today_after_15_pm
            _release_user_asset(self.user.id, self.plan1.id)

        self.assert_success_release(self.unstake_instant_end_request, user=self.user, plan=self.plan1)

    def test_when_instant_end_request_has_no_unstake_transaction_then_no_release_happens(self):
        self.unstake_instant_end_request.delete()

        # running it both after 15 pm and now, ensuring that time does not matter
        _release_user_asset(self.user.id, self.plan1.id)
        with freezegun.freeze_time(self.today_after_15_pm):
            _release_user_asset(self.user.id, self.plan1.id)

        assert (
            StakingTransaction.objects.filter(
                plan=self.plan1, user=self.user, tp=StakingTransaction.TYPES.release
            ).exists()
            is False
        )
        assert (
            Transaction.objects.filter(
                ref_module=134,
                wallet__currency=self.plan1.currency,
                wallet__user=self.user,
                tp=130,
            ).exists()
            is False
        )

    def test_when_user_has_no_staking_release_or_instant_end_then_no_release_transaction_is_created(self):
        self.unstake_instant_end_request.delete()
        self.instant_end_request.delete()

        # running it  both after 15 pm and now, ensuring that time does not matter
        _release_user_asset(self.user.id, self.plan1.id)
        with freezegun.freeze_time(self.today_after_15_pm):
            _release_user_asset(self.user.id, self.plan1.id)

        assert (
            StakingTransaction.objects.filter(
                plan=self.plan1, user=self.user, tp=StakingTransaction.TYPES.release
            ).exists()
            is False
        )
        assert (
            Transaction.objects.filter(
                ref_module=134,
                wallet__currency=self.plan1.currency,
                wallet__user=self.user,
                tp=130,
            ).exists()
            is False
        )

    def test_when_plan_id_is_invalid_then_error_is_raised(self):
        plan_id = Plan.objects.latest('id').id + 100

        with pytest.raises(InvalidPlanId) as _:
            _release_user_asset(self.user.id, plan_id)

        assert (
            StakingTransaction.objects.filter(
                plan_id=plan_id, user=self.user, tp=StakingTransaction.TYPES.release
            ).exists()
            is False
        )

    def test_instant_end_requests_after_today_15_pm_are_not_released_today(self):
        self.unstake_instant_end_request.created_at = ir_now().replace(hour=22, minute=30)
        self.unstake_instant_end_request.save(update_fields=['created_at'])

        with freezegun.freeze_time(self.today_after_15_pm):
            _release_user_asset(self.user.id, self.plan1.id)

        assert (
            StakingTransaction.objects.filter(
                plan=self.plan1, user=self.user, tp=StakingTransaction.TYPES.release
            ).exists()
            is False
        )
        assert (
            Transaction.objects.filter(
                ref_module=134,
                wallet__currency=self.plan1.currency,
                wallet__user=self.user,
                tp=130,
            ).exists()
            is False
        )

    def test_yesterday_after_15_pm_instant_end_requests_are_released_today(self):
        self.unstake_instant_end_request.created_at = ir_now().replace(hour=22, minute=30) - timedelta(days=1)
        self.unstake_instant_end_request.save(update_fields=['created_at'])

        with freezegun.freeze_time(self.today_after_15_pm):
            _release_user_asset(self.user.id, self.plan1.id)

        self.assert_success_release(self.unstake_instant_end_request, user=self.user, plan=self.plan1)

    def test_when_user_stakings_not_finished_unstaking_period_then_no_release_happens(self):
        self.plan2_unstake_transaction.created_at = self.plan2.staked_at + self.plan2.staking_period
        self.plan2_unstake_transaction.save(update_fields=['created_at'])

        # running it  both after 15 pm and now, ensuring that time does not matter
        _release_user_asset(self.user.id, self.plan2.id)
        with freezegun.freeze_time(self.today_after_15_pm):
            _release_user_asset(self.user.id, self.plan2.id)

        assert (
            StakingTransaction.objects.filter(
                plan=self.plan2, user=self.user, tp=StakingTransaction.TYPES.release
            ).exists()
            is False
        )
        assert (
            Transaction.objects.filter(
                ref_module=134,
                wallet__currency=self.plan2.currency,
                wallet__user=self.user,
                tp=130,
            ).exists()
            is False
        )

    def test_when_instant_end_request_that_is_released_before_is_not_released_again(self):
        self.create_staking_transaction(
            user=self.user,
            plan=self.plan1,
            tp=StakingTransaction.TYPES.release,
            amount=self.unstake_instant_end_request.amount,
            parent=self.unstake_instant_end_request,
        )

        _release_user_asset(self.user.id, self.plan1.id)

        assert (
            StakingTransaction.objects.filter(
                plan=self.plan1, user=self.user, tp=StakingTransaction.TYPES.release
            ).count()
            == 1
        )
