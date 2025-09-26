from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import TestCase

from exchange.base.models import Settings
from exchange.staking.errors import (
    AlreadyCreated,
    InvalidAmount,
    ParentIsNotCreated,
    PlanTransactionIsNotCreated,
    TooSoon,
)
from exchange.staking.helpers import StakingFeatureFlags
from exchange.staking.models import (
    ExternalEarningPlatform,
    Plan,
    PlanTransaction,
    StakingTransaction,
    UserPlan,
    UserPlanWalletTransaction,
)
from exchange.staking.service.pay_rewards import _pay_user_reward, pay_all_users_reward
from exchange.wallet.models import Transaction
from tests.staking.utils import StakingTestDataMixin


class PayRewardsTaskTest(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = self.create_user()
        self.user_announced_reward = self.create_staking_transaction(
            user=self.user,
            tp=StakingTransaction.TYPES.announce_reward,
            plan=self.plan,
            created_at=self.plan.staked_at + self.plan.staking_period,
            amount=Decimal('1.5'),
        )
        self.plan_give_reward_transaction = self.create_plan_transaction(
            plan=self.plan,
            amount=Decimal('101'),
            tp=PlanTransaction.TYPES.give_reward,
        )

    def test_pay_user_rewards_successfully_on_staking_plan(self):
        self.plan.external_platform.tp = ExternalEarningPlatform.TYPES.staking
        self.plan.external_platform.save()

        _pay_user_reward(self.user.id, self.plan.id)

        assert PlanTransaction.objects.get(
            plan=self.plan,
            amount=Decimal('99.5'),
            tp=PlanTransaction.TYPES.give_reward,
        )
        staking_reward_transaction = StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            created_at=self.user_announced_reward.created_at,
            tp=StakingTransaction.TYPES.give_reward,
            amount=Decimal('1.5'),
        )
        assert Transaction.objects.get(
            ref_id=staking_reward_transaction.id,
            ref_module=133,
            description='پاداش طرح استیکینگ 1 روزه‌ی بیت‌کوین.',
            amount=Decimal('1.5'),
            wallet__currency=self.plan.currency,
            wallet__user=self.user,
            tp=130,
        )
        assert staking_reward_transaction.wallet_transaction is not None

    def test_pay_user_reward_successfully_on_yield_farming_plan(self):
        self.plan.external_platform.tp = ExternalEarningPlatform.TYPES.yield_aggregator
        self.plan.external_platform.save()

        _pay_user_reward(self.user.id, self.plan.id)

        assert PlanTransaction.objects.get(
            plan=self.plan,
            amount=Decimal('99.5'),
            tp=PlanTransaction.TYPES.give_reward,
        )
        staking_reward_transaction = StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            created_at=self.user_announced_reward.created_at,
            tp=StakingTransaction.TYPES.give_reward,
            amount=Decimal('1.5'),
        )
        assert Transaction.objects.get(
            ref_id=staking_reward_transaction.id,
            ref_module=661537800,
            description='پاداش طرح ییلد فارمینگ 1 روزه‌ی بیت‌کوین.',
            amount=Decimal('1.5'),
            wallet__currency=self.plan.currency,
            wallet__user=self.user,
            tp=160,
        )
        assert staking_reward_transaction.wallet_transaction is not None

    def test_when_user_reward_on_plan_is_already_paid_then_error_is_raised(self):
        self.user_announced_reward.delete()
        self.create_staking_transaction(
            user=self.user, plan=self.plan, tp=StakingTransaction.TYPES.give_reward, amount=Decimal('1')
        )
        with pytest.raises(AlreadyCreated):
            _pay_user_reward(self.user.id, self.plan.id)

        assert PlanTransaction.objects.get(
            plan=self.plan,
            amount=Decimal('101'),
            tp=PlanTransaction.TYPES.give_reward,
        )
        assert (
            Transaction.objects.filter(wallet__user=self.user, wallet__currency=self.plan.currency, tp=130).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                created_at=self.user_announced_reward.created_at,
                tp=StakingTransaction.TYPES.give_reward,
                amount=Decimal('1.5'),
            ).exists()
            == False
        )

    def test_when_plan_has_no_give_reward_transactions_then_error_is_raised(self):
        self.plan_give_reward_transaction.delete()

        with pytest.raises(PlanTransactionIsNotCreated):
            _pay_user_reward(self.user.id, self.plan.id)

        assert (
            Transaction.objects.filter(wallet__user=self.user, wallet__currency=self.plan.currency, tp=130).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                created_at=self.user_announced_reward.created_at,
                tp=StakingTransaction.TYPES.give_reward,
                amount=Decimal('1.5'),
            ).exists()
            == False
        )

    def test_when_user_announce_reward_staking_transaction_is_not_the_final_announce_reward_transaction_then_error_is_raised(
        self,
    ):
        self.user_announced_reward.created_at = self.plan.staked_at
        self.user_announced_reward.save(update_fields=['created_at'])

        with pytest.raises(TooSoon):
            _pay_user_reward(self.user.id, self.plan.id)

        assert PlanTransaction.objects.get(
            plan=self.plan,
            amount=Decimal('101'),
            tp=PlanTransaction.TYPES.give_reward,
        )
        assert (
            Transaction.objects.filter(wallet__user=self.user, wallet__currency=self.plan.currency, tp=130).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                created_at=self.user_announced_reward.created_at,
                tp=StakingTransaction.TYPES.give_reward,
                amount=Decimal('1.5'),
            ).exists()
            == False
        )

    def test_when_plan_has_no_announce_reward_and_pay_reward_then_parent_is_not_created_is_raised(self):
        self.user_announced_reward.delete()

        with pytest.raises(ParentIsNotCreated):
            _pay_user_reward(self.user.id, self.plan.id)

        assert PlanTransaction.objects.get(
            plan=self.plan,
            amount=Decimal('101'),
            tp=PlanTransaction.TYPES.give_reward,
        )
        assert (
            Transaction.objects.filter(wallet__user=self.user, wallet__currency=self.plan.currency, tp=130).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                created_at=self.user_announced_reward.created_at,
                tp=StakingTransaction.TYPES.give_reward,
                amount=Decimal('1.5'),
            ).exists()
            == False
        )

    def test_when_plan_id_does_not_exist_then_error_is_raised(self):
        plan_id = Plan.objects.latest('id').id + 1000

        with pytest.raises(ParentIsNotCreated):
            _pay_user_reward(self.user.id, plan_id)

        assert PlanTransaction.objects.filter(plan_id=plan_id, tp=PlanTransaction.TYPES.give_reward).exists() == False
        assert StakingTransaction.objects.filter(user=self.user, plan_id=plan_id).exists() == False

    def test_when_user_announced_reward_is_greater_than_plan_give_reward_remaining_amount_then_error_is_raised(self):
        self.user_announced_reward.amount = Decimal('101.05')
        self.user_announced_reward.save(update_fields=['amount'])

        with pytest.raises(InvalidAmount):
            _pay_user_reward(self.user.id, self.plan.id)

        assert PlanTransaction.objects.get(
            plan=self.plan,
            amount=Decimal('101'),
            tp=PlanTransaction.TYPES.give_reward,
        )
        assert (
            Transaction.objects.filter(wallet__user=self.user, wallet__currency=self.plan.currency, tp=130).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                created_at=self.user_announced_reward.created_at,
                tp=StakingTransaction.TYPES.give_reward,
                amount=Decimal('101.05'),
            ).exists()
            == False
        )


class PayRewardsTaskNewModelsTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = self.create_user()
        self.user_announced_reward = self.create_staking_transaction(
            user=self.user,
            tp=StakingTransaction.TYPES.announce_reward,
            plan=self.plan,
            created_at=self.plan.staked_at + self.plan.staking_period,
            amount=Decimal('12.5'),
        )
        self.create_staking_transaction(
            user=self.user,
            tp=StakingTransaction.TYPES.stake,
            plan=self.plan,
            amount=Decimal('50.5'),
        )
        self.plan_give_reward_transaction = self.create_plan_transaction(
            plan=self.plan,
            amount=Decimal('201'),
            tp=PlanTransaction.TYPES.give_reward,
            created_at=self.plan.staked_at + self.plan.staking_period,
        )
        self.user_plan = UserPlan.objects.create(
            user=self.user,
            plan=self.plan,
            status=UserPlan.Status.EXTEND_TO_NEXT_CYCLE,
            locked_amount=Decimal('50.5'),
            reward_amount=Decimal('12.5'),
        )

        Settings.set(StakingFeatureFlags.CRONJOB_DUAL_WRITE, 'yes')

    def assert_staking_transactions_success(self, transaction_ref_module: int = 133, transaction_tp: int = 130):
        assert PlanTransaction.objects.get(
            plan=self.plan,
            amount=Decimal('188.5'),
            tp=PlanTransaction.TYPES.give_reward,
        )
        staking_reward_transaction = StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            created_at=self.user_announced_reward.created_at,
            tp=StakingTransaction.TYPES.give_reward,
            amount=Decimal('12.5'),
        )
        assert Transaction.objects.get(
            ref_id=staking_reward_transaction.id,
            ref_module=transaction_ref_module,
            description=f'پاداش {self.plan.fa_description}.',
            amount=Decimal('12.5'),
            wallet__currency=self.plan.currency,
            wallet__user=self.user,
            tp=transaction_tp,
        )
        assert staking_reward_transaction.wallet_transaction is not None

        Settings.set(StakingFeatureFlags.CRONJOB_DUAL_WRITE, 'yes')

    def assert_user_plan_success(self, status=UserPlan.Status.EXTEND_TO_NEXT_CYCLE, wallet_transaction_tp: int = 130):
        user_plan = UserPlan.objects.get(
            user=self.user,
            plan=self.plan,
            status=status,
            locked_amount=Decimal('50.5'),
            reward_amount=Decimal('12.5'),
        )

        assert PlanTransaction.objects.get(
            plan=self.plan,
            amount=Decimal('188.5'),
            tp=PlanTransaction.TYPES.give_reward,
        )
        wallet_transaction = Transaction.objects.get(
            description=f'پاداش {self.plan.fa_description}.',
            amount=Decimal('12.5'),
            wallet__currency=self.plan.currency,
            wallet__user=self.user,
            tp=wallet_transaction_tp,
        )
        assert UserPlanWalletTransaction.objects.get(
            user_plan=user_plan,
            amount=Decimal('12.5'),
            tp=UserPlanWalletTransaction.Type.REWARD,
            wallet_transaction=wallet_transaction,
            user_plan_request__isnull=True,
        )

    def test_pay_user_rewards_successfully_on_staking_plan_creates_both_models_instances(self):
        self.plan.external_platform.tp = ExternalEarningPlatform.TYPES.staking
        self.plan.external_platform.save()

        pay_all_users_reward(self.plan.id)

        self.assert_staking_transactions_success()
        self.assert_user_plan_success()

    def test_pay_user_reward_successfully_on_yield_farming_plan_creates_both_models_instances(self):
        self.plan.external_platform.tp = ExternalEarningPlatform.TYPES.yield_aggregator
        self.plan.external_platform.save()

        pay_all_users_reward(self.plan.id)

        self.assert_staking_transactions_success(transaction_ref_module=661537800, transaction_tp=160)
        self.assert_user_plan_success(wallet_transaction_tp=160)

    def test_pay_user_reward_success_when_user_plan_is_release(self):
        self.user_plan.status = UserPlan.Status.RELEASED
        self.user_plan.save(update_fields=['status'])

        pay_all_users_reward(self.plan.id)

        self.assert_user_plan_success(status=UserPlan.Status.RELEASED)

    def test_pay_user_reward_success_when_user_plan_is_pending_release(self):
        self.user_plan.status = UserPlan.Status.PENDING_RELEASE
        self.user_plan.save(update_fields=['status'])

        pay_all_users_reward(self.plan.id)

        self.assert_user_plan_success(status=UserPlan.Status.PENDING_RELEASE)

    @patch('exchange.staking.errors.report_exception')
    def test_when_user_plan_has_reward_wallet_transaction_then_reward_is_not_payed_again_and_error_is_raised(
        self, mocked_report_exception
    ):
        UserPlanWalletTransaction.objects.create(
            user_plan=self.user_plan,
            amount=Decimal('5.5'),
            tp=UserPlanWalletTransaction.Type.REWARD,
        )

        pay_all_users_reward(self.plan.id)

        mocked_report_exception.assert_called_once()
        assert (
            UserPlanWalletTransaction.objects.filter(
                user_plan=self.user_plan,
                tp=UserPlanWalletTransaction.Type.REWARD,
            ).count()
            == 1
        )

    @patch('exchange.staking.admin_notifier.notify_or_raise_exception')
    def test_when_plan_has_no_give_reward_transactions_then_error_is_raised(self, mocked_report_exception):
        self.plan_give_reward_transaction.delete()

        pay_all_users_reward(self.plan.id)

        mocked_report_exception.assert_called_once()
        assert (
            UserPlanWalletTransaction.objects.filter(
                user_plan=self.user_plan,
                tp=UserPlanWalletTransaction.Type.REWARD,
            ).count()
            == 0
        )
        assert Transaction.objects.filter(wallet__user=self.user, wallet__currency=self.plan.currency).exists() == False

    @patch('exchange.staking.errors.report_exception')
    def test_when_calculated_user_plan_is_not_final_reward_calculation_after_staking_period_then_error_is_raised(
        self, mocked_report_exception
    ):
        self.plan_give_reward_transaction.created_at = self.plan.staked_at
        self.plan_give_reward_transaction.save(update_fields=['created_at'])

        pay_all_users_reward(self.plan.id)

        mocked_report_exception.assert_called_once()
        assert (
            UserPlanWalletTransaction.objects.filter(
                user_plan=self.user_plan,
                tp=UserPlanWalletTransaction.Type.REWARD,
            ).count()
            == 0
        )

    @patch('exchange.staking.errors.report_exception')
    def test_when_user_plan_reward_amount_is_zero_then_error_is_raised(self, mocked_report_exception):
        self.user_plan.reward_amount = 0
        self.user_plan.save(update_fields=['reward_amount'])

        pay_all_users_reward(self.plan.id)

        mocked_report_exception.assert_called_once()
        assert (
            UserPlanWalletTransaction.objects.filter(
                user_plan=self.user_plan,
                tp=UserPlanWalletTransaction.Type.REWARD,
            ).count()
            == 0
        )

    def test_when_plan_id_does_not_exist_then_no_reward_is_payed(self):
        plan_id = Plan.objects.latest('id').id + 100

        pay_all_users_reward(plan_id)

        assert (
            UserPlanWalletTransaction.objects.filter(
                user_plan__plan_id=plan_id,
                tp=UserPlanWalletTransaction.Type.REWARD,
            ).count()
            == 0
        )

    @patch('exchange.staking.errors.report_exception')
    def test_when_user_plan_reward_is_greater_than_plan_plan_give_reward_remaining_amount_then_error_is_raised(
        self, mocked_report_exception
    ):
        self.user_plan.reward_amount = Decimal('500')
        self.user_plan.save(update_fields=['reward_amount'])

        pay_all_users_reward(self.plan.id)

        mocked_report_exception.assert_called_once()
        assert (
            UserPlanWalletTransaction.objects.filter(
                user_plan=self.user_plan,
                tp=UserPlanWalletTransaction.Type.REWARD,
            ).count()
            == 0
        )

    def test_when_staking_cronjob_dual_write_is_not_enabled_then_only_old_model_instances_are_created(self):
        Settings.set(StakingFeatureFlags.CRONJOB_DUAL_WRITE, 'no')
        self.plan.external_platform.tp = ExternalEarningPlatform.TYPES.staking
        self.plan.external_platform.save()

        pay_all_users_reward(self.plan.id)

        self.assert_staking_transactions_success()
        assert (
            UserPlanWalletTransaction.objects.filter(
                user_plan=self.user_plan,
                tp=UserPlanWalletTransaction.Type.REWARD,
            ).count()
            == 0
        )

    @patch('exchange.staking.service.pay_rewards.Settings.get_flag')
    @patch('exchange.staking.errors.report_exception')
    def test_when_pay_user_plan_reward_function_raises_unknown_error_then_old_model_instances_are_created_successfully(
        self, mocked_report_exception, mocked_inner_pay_user_plan_reward
    ):
        mocked_inner_pay_user_plan_reward.side_effect = Exception
        self.plan.external_platform.tp = ExternalEarningPlatform.TYPES.staking
        self.plan.external_platform.save()

        pay_all_users_reward(self.plan.id)

        mocked_report_exception.assert_called_once()
        self.assert_staking_transactions_success()
        assert (
            UserPlanWalletTransaction.objects.filter(
                user_plan=self.user_plan,
                tp=UserPlanWalletTransaction.Type.REWARD,
            ).count()
            == 0
        )

    @patch('exchange.staking.errors.report_exception')
    def test_when_user_plan_is_in_canceled_status_then_error_is_raised(self, mocked_report_exception):
        self.user_plan.status = UserPlan.Status.USER_CANCELED
        self.user_plan.save(update_fields=['status'])

        pay_all_users_reward(self.plan.id)

        mocked_report_exception.assert_called_once()
        assert (
            UserPlanWalletTransaction.objects.filter(
                user_plan=self.user_plan,
                tp=UserPlanWalletTransaction.Type.REWARD,
            ).count()
            == 0
        )

    @patch('exchange.staking.errors.report_exception')
    def test_when_user_plan_is_in_reject_status_then_error_is_raised(self, mocked_report_exception):
        self.user_plan.status = UserPlan.Status.ADMIN_REJECTED
        self.user_plan.save(update_fields=['status'])

        pay_all_users_reward(self.plan.id)

        mocked_report_exception.assert_called_once()
        assert (
            UserPlanWalletTransaction.objects.filter(
                user_plan=self.user_plan,
                tp=UserPlanWalletTransaction.Type.REWARD,
            ).count()
            == 0
        )

    @patch('exchange.staking.errors.report_exception')
    def test_when_user_plan_is_in_requested_status_then_error_is_raised(self, mocked_report_exception):
        self.user_plan.status = UserPlan.Status.REQUESTED
        self.user_plan.save(update_fields=['status'])

        pay_all_users_reward(self.plan.id)

        mocked_report_exception.assert_called_once()
        assert (
            UserPlanWalletTransaction.objects.filter(
                user_plan=self.user_plan,
                tp=UserPlanWalletTransaction.Type.REWARD,
            ).count()
            == 0
        )

    @patch('exchange.staking.errors.report_exception')
    def test_when_user_plan_is_in_locked_status_then_error_is_raised(self, mocked_report_exception):
        self.user_plan.status = UserPlan.Status.LOCKED
        self.user_plan.save(update_fields=['status'])

        pay_all_users_reward(self.plan.id)

        mocked_report_exception.assert_called_once()
        assert (
            UserPlanWalletTransaction.objects.filter(
                user_plan=self.user_plan,
                tp=UserPlanWalletTransaction.Type.REWARD,
            ).count()
            == 0
        )

    @patch('exchange.staking.errors.report_exception')
    def test_when_user_plan_is_in_extended_from_previous_cycle_status_then_error_is_raised(
        self, mocked_report_exception
    ):
        self.user_plan.status = UserPlan.Status.EXTEND_FROM_PREVIOUS_CYCLE
        self.user_plan.save(update_fields=['status'])

        pay_all_users_reward(self.plan.id)

        mocked_report_exception.assert_called_once()
        assert (
            UserPlanWalletTransaction.objects.filter(
                user_plan=self.user_plan,
                tp=UserPlanWalletTransaction.Type.REWARD,
            ).count()
            == 0
        )

    @patch('exchange.staking.errors.report_exception')
    def test_when_user_plan_locked_amount_is_zero_then_error_is_raised(self, mocked_report_exception):
        self.user_plan.reward_amount = 0
        self.user_plan.save(update_fields=['reward_amount'])

        pay_all_users_reward(self.plan.id)

        mocked_report_exception.assert_called_once()
        assert (
            UserPlanWalletTransaction.objects.filter(
                user_plan=self.user_plan,
                tp=UserPlanWalletTransaction.Type.REWARD,
            ).count()
            == 0
        )
