from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import TestCase

from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from exchange.staking.errors import AlreadyCreated, InvalidPlanId
from exchange.staking.helpers import StakingFeatureFlags
from exchange.staking.models import Plan, PlanTransaction, StakingTransaction, UserPlan
from exchange.staking.service.announce_reward import announce_all_users_rewards
from tests.staking.utils import StakingTestDataMixin


class AnnounceRewardsServiceTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.plan.opened_at = ir_now() - timedelta(days=3)
        self.plan.staked_at = ir_now() - timedelta(days=3)
        self.plan.staking_period = timedelta(days=2)
        self.plan.reward_announcement_period = timedelta(days=1)
        self.plan.save()

        self.user1 = self.create_user()
        self.user2 = self.create_user()
        self.create_staking_transaction(
            user=self.user1, tp=StakingTransaction.TYPES.stake, amount=Decimal('10.00'), plan=self.plan
        )
        self.create_staking_transaction(
            user=self.user2, tp=StakingTransaction.TYPES.stake, amount=Decimal('12.00'), plan=self.plan
        )

    def test_when_plan_announce_reward_with_exact_announce_reward_timestamp_exists_then_error_is_raised(self):
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.announce_reward,
            amount=Decimal('100'),
            parent_transaction=None,
            created_at=self.plan.staked_at + self.plan.staking_period,
        )

        with pytest.raises(AlreadyCreated):
            announce_all_users_rewards(self.plan.id)

        assert (
            StakingTransaction.objects.filter(tp=StakingTransaction.TYPES.announce_reward, plan=self.plan).exists()
            is False
        )
        assert PlanTransaction.objects.filter(tp=PlanTransaction.TYPES.announce_reward, plan=self.plan).count() == 1

    def test_when_no_announce_reward_and_fetch_reward_exists_then_users_announce_reward_transactions_are_created_successfully_with_zero_amount(
        self,
    ):
        announce_all_users_rewards(self.plan.id)

        plan_announce_reward = PlanTransaction.objects.get(
            plan=self.plan,
            tp=PlanTransaction.TYPES.announce_reward,
            created_at=self.plan.staked_at + self.plan.staking_period,
            amount=Decimal('0'),
            parent=None,
        )
        assert StakingTransaction.objects.get(
            user=self.user1,
            plan=self.plan,
            tp=StakingTransaction.TYPES.announce_reward,
            created_at=plan_announce_reward.created_at,
            plan_transaction=plan_announce_reward,
            amount=Decimal('0'),
            parent=None,
        )
        assert StakingTransaction.objects.get(
            user=self.user2,
            plan=self.plan,
            tp=StakingTransaction.TYPES.announce_reward,
            created_at=plan_announce_reward.created_at,
            plan_transaction=plan_announce_reward,
            amount=Decimal('0'),
            parent=None,
        )

    def test_first_announcement_reward_when_system_has_fetched_rewards(self):
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('20'),
            created_at=self.plan.staked_at + self.plan.staking_period - self.plan.reward_announcement_period,
        )
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('30'),
            created_at=self.plan.staked_at + self.plan.staking_period,
        )

        announce_all_users_rewards(self.plan.id)

        plan_announce_reward = PlanTransaction.objects.get(
            plan=self.plan,
            tp=PlanTransaction.TYPES.announce_reward,
            created_at=self.plan.staked_at + self.plan.staking_period,
            amount=Decimal('8.0'),
            parent=None,
        )
        assert StakingTransaction.objects.get(
            user=self.user1,
            plan=self.plan,
            tp=StakingTransaction.TYPES.announce_reward,
            created_at=plan_announce_reward.created_at,
            plan_transaction=plan_announce_reward,
            amount=Decimal('0.80'),
            parent=None,
        )
        assert StakingTransaction.objects.get(
            user=self.user2,
            plan=self.plan,
            tp=StakingTransaction.TYPES.announce_reward,
            created_at=plan_announce_reward.created_at,
            plan_transaction=plan_announce_reward,
            amount=Decimal('0.96'),
            parent=None,
        )

    def test_announce_users_rewards_when_plan_has_both_fetch_rewards_and_previously_announced_rewards(self):
        previous_plan_announce_reward = self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.announce_reward,
            amount=Decimal('44'),
            parent_transaction=None,
            created_at=self.plan.staked_at + self.plan.reward_announcement_period,
        )
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('11'),
            created_at=self.plan.staked_at + self.plan.staking_period - self.plan.reward_announcement_period,
        )
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('26'),
            created_at=self.plan.staked_at + self.plan.staking_period,
        )

        announce_all_users_rewards(self.plan.id)

        plan_announce_reward = PlanTransaction.objects.get(
            plan=self.plan,
            tp=PlanTransaction.TYPES.announce_reward,
            created_at=self.plan.staked_at + self.plan.staking_period,
            amount=Decimal('56.00'),
            parent=previous_plan_announce_reward,
        )
        assert StakingTransaction.objects.get(
            user=self.user1,
            plan=self.plan,
            tp=StakingTransaction.TYPES.announce_reward,
            created_at=plan_announce_reward.created_at,
            plan_transaction=plan_announce_reward,
            amount=Decimal('5.60'),
            parent=None,
        )
        assert StakingTransaction.objects.get(
            user=self.user2,
            plan=self.plan,
            tp=StakingTransaction.TYPES.announce_reward,
            created_at=plan_announce_reward.created_at,
            plan_transaction=plan_announce_reward,
            amount=Decimal('6.7200'),
            parent=None,
        )

    def test_when_plan_id_is_invalid_then_error_is_raised(self):
        plan_id = Plan.objects.latest('id').id + 100

        with pytest.raises(InvalidPlanId):
            announce_all_users_rewards(plan_id)

        assert (
            StakingTransaction.objects.filter(tp=StakingTransaction.TYPES.announce_reward, plan_id=plan_id).exists()
            is False
        )
        assert (
            PlanTransaction.objects.filter(tp=PlanTransaction.TYPES.announce_reward, plan_id=plan_id).exists() is False
        )

    def test_announce_user_rewards_multiple_times_adds_existing_staking_transactions_announce_rewards_as_parents(self):
        previous_plan_announce_reward = self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.announce_reward,
            amount=Decimal('44'),
            parent_transaction=None,
            created_at=self.plan.staked_at + self.plan.reward_announcement_period,
        )
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('11'),
            created_at=self.plan.staked_at + self.plan.staking_period - self.plan.reward_announcement_period,
        )
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('26'),
            created_at=self.plan.staked_at + self.plan.staking_period,
        )
        user1_existing_announce_reward = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.announce_reward,
            amount=Decimal('1.00'),
            user=self.user1,
            plan=self.plan,
        )
        user2_existing_announce_reward = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.announce_reward,
            amount=Decimal('1.00'),
            user=self.user2,
            plan=self.plan,
        )

        announce_all_users_rewards(self.plan.id)

        plan_announce_reward = PlanTransaction.objects.get(
            plan=self.plan,
            tp=PlanTransaction.TYPES.announce_reward,
            created_at=self.plan.staked_at + self.plan.staking_period,
            amount=Decimal('56.00'),
            parent=previous_plan_announce_reward,
        )
        assert StakingTransaction.objects.get(
            user=self.user1,
            plan=self.plan,
            tp=StakingTransaction.TYPES.announce_reward,
            created_at=plan_announce_reward.created_at,
            plan_transaction=plan_announce_reward,
            amount=Decimal('5.60'),
            parent=user1_existing_announce_reward,
        )
        assert StakingTransaction.objects.get(
            user=self.user2,
            plan=self.plan,
            tp=StakingTransaction.TYPES.announce_reward,
            created_at=plan_announce_reward.created_at,
            plan_transaction=plan_announce_reward,
            amount=Decimal('6.7200'),
            parent=user2_existing_announce_reward,
        )


class AnnounceRewardsServiceNewModelsTest(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.plan.opened_at = ir_now() - timedelta(days=3)
        self.plan.staked_at = ir_now() - timedelta(days=3)
        self.plan.staking_period = timedelta(days=2)
        self.plan.reward_announcement_period = timedelta(days=1)
        self.plan.save()

        self.user1 = self.create_user()
        self.user2 = self.create_user()
        self.user1_stake_transaction = self.create_staking_transaction(
            user=self.user1, tp=StakingTransaction.TYPES.stake, amount=Decimal('10.00'), plan=self.plan
        )
        self.user2_stake_transaction = self.create_staking_transaction(
            user=self.user2, tp=StakingTransaction.TYPES.stake, amount=Decimal('12.00'), plan=self.plan
        )
        self.user_plan1 = UserPlan.objects.create(
            user=self.user1,
            plan=self.plan,
            status=UserPlan.Status.LOCKED,
            locked_amount=Decimal('10.0'),
            reward_amount=Decimal('1.0'),
        )
        self.user_plan2 = UserPlan.objects.create(
            user=self.user2,
            plan=self.plan,
            status=UserPlan.Status.LOCKED,
            locked_amount=Decimal('12.0'),
            reward_amount=Decimal('2.0'),
        )

        Settings.set(StakingFeatureFlags.CRONJOB_DUAL_WRITE, 'yes')

    def assert_staking_transactions_success(
        self,
        plan_reward_amount: Decimal,
        user1_reward_amount: Decimal,
        user2_reward_amount: Decimal,
        plan_reward_parent: PlanTransaction = None,
    ):
        plan_announce_reward = PlanTransaction.objects.get(
            plan=self.plan,
            tp=PlanTransaction.TYPES.announce_reward,
            created_at=self.plan.staked_at + self.plan.staking_period,
            amount=plan_reward_amount,
            parent=plan_reward_parent,
        )
        assert StakingTransaction.objects.get(
            user=self.user1,
            plan=self.plan,
            tp=StakingTransaction.TYPES.announce_reward,
            created_at=plan_announce_reward.created_at,
            plan_transaction=plan_announce_reward,
            amount=user1_reward_amount,
            parent=None,
        )
        assert StakingTransaction.objects.get(
            user=self.user2,
            plan=self.plan,
            tp=StakingTransaction.TYPES.announce_reward,
            created_at=plan_announce_reward.created_at,
            plan_transaction=plan_announce_reward,
            amount=user2_reward_amount,
            parent=None,
        )

    def assert_user_plans_reward_amount(self, user_plan1_reward_amount: Decimal, user_plan2_reward_amount: Decimal):
        self.user_plan1.refresh_from_db(fields=['reward_amount'])
        self.user_plan2.refresh_from_db(fields=['reward_amount'])

        assert self.user_plan1.reward_amount == user_plan1_reward_amount
        assert self.user_plan2.reward_amount == user_plan2_reward_amount

    def test_when_plan_has_both_fetch_rewards_and_previously_announced_rewards_then_update_rewards_successfully(self):
        previouse_plna_reward = self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.announce_reward,
            amount=Decimal('44'),
            parent_transaction=None,
            created_at=self.plan.staked_at + self.plan.reward_announcement_period,
        )
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('11'),
            created_at=self.plan.staked_at + self.plan.staking_period - self.plan.reward_announcement_period,
        )
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('26'),
            created_at=self.plan.staked_at + self.plan.staking_period,
        )

        announce_all_users_rewards(self.plan.id)

        self.assert_staking_transactions_success(
            plan_reward_amount=Decimal('56.00'),
            user1_reward_amount=Decimal('5.60'),
            user2_reward_amount=Decimal('6.7200'),
            plan_reward_parent=previouse_plna_reward,
        )
        self.assert_user_plans_reward_amount(
            user_plan1_reward_amount=Decimal('5.60'),
            user_plan2_reward_amount=Decimal('6.7200'),
        )

    def test_when_no_announce_reward_and_fetch_reward_exists_then_both_model_instances_are_created_with_zero_reward_amount_successfully(
        self,
    ):
        announce_all_users_rewards(self.plan.id)

        self.assert_staking_transactions_success(
            plan_reward_amount=Decimal('0'),
            user1_reward_amount=Decimal('0'),
            user2_reward_amount=Decimal('0'),
        )
        self.assert_user_plans_reward_amount(
            user_plan1_reward_amount=Decimal('0'),
            user_plan2_reward_amount=Decimal('0'),
        )

    def test_announce_first_reward_when_system_has_fetched_rewards_then_both_models_are_updated_successfully(self):
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('20'),
            created_at=self.plan.staked_at + self.plan.staking_period - self.plan.reward_announcement_period,
        )
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('30'),
            created_at=self.plan.staked_at + self.plan.staking_period,
        )

        announce_all_users_rewards(self.plan.id)

        self.assert_staking_transactions_success(
            plan_reward_amount=Decimal('8.0'),
            user1_reward_amount=Decimal('0.80'),
            user2_reward_amount=Decimal('0.96'),
        )
        self.assert_user_plans_reward_amount(
            user_plan1_reward_amount=Decimal('0.80'),
            user_plan2_reward_amount=Decimal('0.96'),
        )

    def test_when_dual_write_feature_flag_is_disabled_then_only_staking_transactions_are_created(self):
        Settings.set(StakingFeatureFlags.CRONJOB_DUAL_WRITE, 'no')

        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('20'),
            created_at=self.plan.staked_at + self.plan.staking_period - self.plan.reward_announcement_period,
        )
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('30'),
            created_at=self.plan.staked_at + self.plan.staking_period,
        )

        announce_all_users_rewards(self.plan.id)

        self.assert_staking_transactions_success(
            plan_reward_amount=Decimal('8.0'),
            user1_reward_amount=Decimal('0.80'),
            user2_reward_amount=Decimal('0.96'),
        )
        # no update for user plan rewards
        self.assert_user_plans_reward_amount(
            user_plan1_reward_amount=Decimal('1.0'),
            user_plan2_reward_amount=Decimal('2.0'),
        )

    @patch('exchange.staking.errors.report_exception')
    @patch('exchange.staking.service.announce_reward.Settings.get_flag')
    def test_when_update_user_plan_reward_function_raises_unknown_error_then_only_staking_transactions_are_created(
        self, mocked_internal_update_user_plan_function, mocked_report_exception
    ):
        mocked_internal_update_user_plan_function.side_effect = Exception

        previouse_plna_reward = self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.announce_reward,
            amount=Decimal('44'),
            parent_transaction=None,
            created_at=self.plan.staked_at + self.plan.reward_announcement_period,
        )
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('11'),
            created_at=self.plan.staked_at + self.plan.staking_period - self.plan.reward_announcement_period,
        )
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('26'),
            created_at=self.plan.staked_at + self.plan.staking_period,
        )

        announce_all_users_rewards(self.plan.id)

        mocked_report_exception.assert_called_once()
        self.assert_staking_transactions_success(
            plan_reward_amount=Decimal('56.00'),
            user1_reward_amount=Decimal('5.60'),
            user2_reward_amount=Decimal('6.7200'),
            plan_reward_parent=previouse_plna_reward,
        )
        # no update for user plans reward
        self.assert_user_plans_reward_amount(
            user_plan1_reward_amount=Decimal('1.0'),
            user_plan2_reward_amount=Decimal('2.0'),
        )

    def test_when_plan_announce_reward_with_exact_announce_reward_timestamp_exists_then_error_is_raised(self):
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.announce_reward,
            amount=Decimal('101.7'),
            parent_transaction=None,
            created_at=self.plan.staked_at + self.plan.staking_period,
        )

        with pytest.raises(AlreadyCreated):
            announce_all_users_rewards(self.plan.id)

        assert (
            StakingTransaction.objects.filter(tp=StakingTransaction.TYPES.announce_reward, plan=self.plan).exists()
            is False
        )
        assert PlanTransaction.objects.filter(tp=PlanTransaction.TYPES.announce_reward, plan=self.plan).count() == 1
        # no update for user plans reward
        self.assert_user_plans_reward_amount(
            user_plan1_reward_amount=Decimal('1.0'),
            user_plan2_reward_amount=Decimal('2.0'),
        )

    def test_when_plan_id_is_invalid_then_error_is_raised(self):
        plan_id = Plan.objects.latest('id').id + 100

        with pytest.raises(InvalidPlanId):
            announce_all_users_rewards(plan_id)

        assert (
            StakingTransaction.objects.filter(tp=StakingTransaction.TYPES.announce_reward, plan_id=plan_id).exists()
            is False
        )
        assert (
            PlanTransaction.objects.filter(tp=PlanTransaction.TYPES.announce_reward, plan_id=plan_id).exists() is False
        )
        # no update for user plans reward
        self.assert_user_plans_reward_amount(
            user_plan1_reward_amount=Decimal('1.0'),
            user_plan2_reward_amount=Decimal('2.0'),
        )

    def test_announce_rewards_multiple_times_sets_reward_amounts_for_user_plans(self):
        self.assert_user_plans_reward_amount(
            user_plan1_reward_amount=Decimal('1.0'),
            user_plan2_reward_amount=Decimal('2.0'),
        )

        announce_all_users_rewards(self.plan.id)

        self.assert_user_plans_reward_amount(
            user_plan1_reward_amount=Decimal('0'),
            user_plan2_reward_amount=Decimal('0'),
        )

        # plan has now fetch rewards and no announce rewards at this time
        PlanTransaction.objects.filter(tp=PlanTransaction.TYPES.announce_reward, plan=self.plan).delete()
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('20'),
            created_at=self.plan.staked_at + self.plan.staking_period - self.plan.reward_announcement_period,
        )
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('30'),
            created_at=self.plan.staked_at + self.plan.staking_period,
        )

        announce_all_users_rewards(self.plan.id)

        self.assert_user_plans_reward_amount(
            user_plan1_reward_amount=Decimal('0.80'),
            user_plan2_reward_amount=Decimal('0.96'),
        )

    def test_when_user_plan_is_rejected_then_no_reward_is_set_for_user_plans(self):
        self.user_plan1.status = UserPlan.Status.ADMIN_REJECTED
        self.user_plan1.save(update_fields=['status'])

        announce_all_users_rewards(self.plan.id)

        self.assert_staking_transactions_success(
            plan_reward_amount=Decimal('0'),
            user1_reward_amount=Decimal('0'),
            user2_reward_amount=Decimal('0'),
        )
        # no update for user1  reward
        self.assert_user_plans_reward_amount(
            user_plan1_reward_amount=Decimal('1.0'),
            user_plan2_reward_amount=Decimal('0.0'),
        )

    def test_when_user_plan_is_requested_then_no_reward_is_set_for_user_plans(self):
        self.user_plan1.status = UserPlan.Status.REQUESTED
        self.user_plan1.save(update_fields=['status'])

        announce_all_users_rewards(self.plan.id)

        self.assert_staking_transactions_success(
            plan_reward_amount=Decimal('0'),
            user1_reward_amount=Decimal('0'),
            user2_reward_amount=Decimal('0'),
        )
        # no update for user1  reward
        self.assert_user_plans_reward_amount(
            user_plan1_reward_amount=Decimal('1.0'),
            user_plan2_reward_amount=Decimal('0.0'),
        )

    def test_when_user_plan_is_canceled_then_no_reward_is_set_for_user_plans(self):
        self.user_plan1.status = UserPlan.Status.USER_CANCELED
        self.user_plan1.save(update_fields=['status'])

        announce_all_users_rewards(self.plan.id)

        self.assert_staking_transactions_success(
            plan_reward_amount=Decimal('0'),
            user1_reward_amount=Decimal('0'),
            user2_reward_amount=Decimal('0'),
        )
        # no update for user1  reward
        self.assert_user_plans_reward_amount(
            user_plan1_reward_amount=Decimal('1.0'),
            user_plan2_reward_amount=Decimal('0.0'),
        )
