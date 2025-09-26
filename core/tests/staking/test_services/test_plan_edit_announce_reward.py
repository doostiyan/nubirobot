from decimal import Decimal
from typing import Union
from unittest.mock import patch

import pytest
from django.test import TestCase

from exchange.base.models import Settings
from exchange.staking.errors import InvalidPlanId
from exchange.staking.helpers import StakingFeatureFlags
from exchange.staking.models import Plan, PlanTransaction, StakingTransaction, UserPlan
from exchange.staking.service.announce_reward import edit_last_announced_reward
from tests.staking.utils import StakingTestDataMixin


class PlanEditAnnounceRewardTest(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.plan.total_capacity = Decimal('10')
        self.plan.save(update_fields=('total_capacity',))

        self.plan_announce_reward_transaction = self.create_plan_transaction(
            plan=self.plan, tp=PlanTransaction.TYPES.announce_reward, amount=Decimal('574')
        )

        # create users with stake transactions and announce reward transaction
        self.user1 = self.create_user()
        self.user1_stake_transaction = self.create_staking_transaction(
            user=self.user1,
            plan=self.plan,
            amount=Decimal('1'),
            tp=StakingTransaction.TYPES.stake,
        )
        self.user1_reward_transaction = self.create_staking_transaction(
            user=self.user1,
            plan=self.plan,
            amount=Decimal('574'),
            tp=StakingTransaction.TYPES.announce_reward,
            plan_transaction=self.plan_announce_reward_transaction,
        )

        self.user2 = self.create_user()
        self.user2_stake_transaction = self.create_staking_transaction(
            user=self.user2,
            plan=self.plan,
            amount=Decimal('2'),
            tp=StakingTransaction.TYPES.stake,
        )
        self.user2_reward_transaction = self.create_staking_transaction(
            user=self.user2,
            plan=self.plan,
            amount=Decimal('574'),
            tp=StakingTransaction.TYPES.announce_reward,
            plan_transaction=self.plan_announce_reward_transaction,
        )

        self.user3 = self.create_user()
        self.user3_stake_transaction = self.create_staking_transaction(
            user=self.user3,
            plan=self.plan,
            amount=Decimal('4'),
            tp=StakingTransaction.TYPES.stake,
        )
        self.user3_reward_transaction = self.create_staking_transaction(
            user=self.user3,
            plan=self.plan,
            amount=Decimal('574'),
            tp=StakingTransaction.TYPES.announce_reward,
            plan_transaction=self.plan_announce_reward_transaction,
        )

    @staticmethod
    def assert_transaction_amount(transaction: Union[PlanTransaction, StakingTransaction], amount: Decimal):
        transaction.refresh_from_db(fields=['amount'])
        assert transaction.amount == amount

    def test_success_with_none_zero_amount_when_both_plan_and_users_have_existing_none_zero_reward_transaction(self):
        edit_last_announced_reward(self.plan.id, Decimal('0.8'))

        self.assert_transaction_amount(self.plan_announce_reward_transaction, Decimal('0.8'))
        self.assert_transaction_amount(self.user1_reward_transaction, Decimal('0.08'))
        self.assert_transaction_amount(self.user2_reward_transaction, Decimal('0.16'))
        self.assert_transaction_amount(self.user3_reward_transaction, Decimal('0.32'))

    def test_when_new_amount_is_zero_then_both_plan_and_users_reward_transaction_amount_become_zero(self):
        edit_last_announced_reward(self.plan.id, Decimal('0'))

        self.assert_transaction_amount(self.plan_announce_reward_transaction, Decimal('0.0'))
        self.assert_transaction_amount(self.user1_reward_transaction, Decimal('0.0'))
        self.assert_transaction_amount(self.user2_reward_transaction, Decimal('0.0'))
        self.assert_transaction_amount(self.user3_reward_transaction, Decimal('0.0'))

    def test_success_when_existing_plan_transaction_amount_is_zero_then_new_rewards_are_not_zero(self):
        self.plan_announce_reward_transaction.amount = Decimal('0')
        self.plan_announce_reward_transaction.save(update_fields=['amount'])

        edit_last_announced_reward(self.plan.id, Decimal('0.8'))

        self.assert_transaction_amount(self.user1_reward_transaction, Decimal('0.08'))
        self.assert_transaction_amount(self.user2_reward_transaction, Decimal('0.16'))
        self.assert_transaction_amount(self.user3_reward_transaction, Decimal('0.32'))

    def test_only_last_announce_reward_transaction_changes_and_parent_transactions_stay_unchanged(self):
        new_plan_announce_transaction = self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.announce_reward,
            amount=Decimal('21'),
            parent_transaction=self.plan_announce_reward_transaction,
        )
        new_user1_reward_transaction = self.create_staking_transaction(
            user=self.user1,
            plan=self.plan,
            amount=Decimal('22'),
            tp=StakingTransaction.TYPES.announce_reward,
            parent=self.user1_reward_transaction,
            plan_transaction=new_plan_announce_transaction,
        )
        new_user2_reward_transaction = self.create_staking_transaction(
            user=self.user2,
            plan=self.plan,
            amount=Decimal('88'),
            tp=StakingTransaction.TYPES.announce_reward,
            parent=self.user2_reward_transaction,
            plan_transaction=new_plan_announce_transaction,
        )
        new_user3_reward_transaction = self.create_staking_transaction(
            user=self.user3,
            plan=self.plan,
            amount=Decimal('274'),
            tp=StakingTransaction.TYPES.announce_reward,
            parent=self.user1_reward_transaction,
            plan_transaction=new_plan_announce_transaction,
        )

        edit_last_announced_reward(self.plan.id, Decimal('0.8'))

        self.assert_transaction_amount(self.user1_reward_transaction, Decimal('574'))
        self.assert_transaction_amount(self.user2_reward_transaction, Decimal('574'))
        self.assert_transaction_amount(self.user3_reward_transaction, Decimal('574'))
        self.assert_transaction_amount(self.plan_announce_reward_transaction, Decimal('574'))

        self.assert_transaction_amount(new_plan_announce_transaction, Decimal('0.8'))
        self.assert_transaction_amount(new_user1_reward_transaction, Decimal('0.08'))
        self.assert_transaction_amount(new_user2_reward_transaction, Decimal('0.16'))
        self.assert_transaction_amount(new_user3_reward_transaction, Decimal('0.320'))

    def test_when_plan_id_does_not_exist_then_error_is_raised(self):
        plan_id = Plan.objects.latest('id').id + 10

        with pytest.raises(InvalidPlanId):
            edit_last_announced_reward(plan_id, Decimal('0.8'))

    def test_when_plan_has_no_announce_reward_transaction_then_error_is_raised(self):
        plan = self.create_plan(**self.get_plan_kwargs())

        with pytest.raises(PlanTransaction.DoesNotExist):
            edit_last_announced_reward(plan.id, Decimal('0.8'))

        assert PlanTransaction.objects.filter(plan=plan).exists() is False

    def test_when_users_have_no_announce_reward_transaction_then_nothing_happens(self):
        plan = self.create_plan(**self.get_plan_kwargs())
        self.create_plan_transaction(plan=plan, tp=PlanTransaction.TYPES.announce_reward, amount=Decimal('300'))

        edit_last_announced_reward(plan.id, Decimal('0.8'))

        assert StakingTransaction.objects.filter(plan=plan).exists() is False


class PlanEditAnnounceRewardNewModelsTest(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.plan.total_capacity = Decimal('10')
        self.plan.save(update_fields=('total_capacity',))

        self.plan_announce_reward_transaction = self.create_plan_transaction(
            plan=self.plan, tp=PlanTransaction.TYPES.announce_reward, amount=Decimal('574')
        )
        # create users with stake transactions and announce reward transaction
        self.user1 = self.create_user()
        self.user1_stake_transaction = self.create_staking_transaction(
            user=self.user1,
            plan=self.plan,
            amount=Decimal('1'),
            tp=StakingTransaction.TYPES.stake,
        )
        self.user1_reward_transaction = self.create_staking_transaction(
            user=self.user1,
            plan=self.plan,
            amount=Decimal('54.0'),
            tp=StakingTransaction.TYPES.announce_reward,
            plan_transaction=self.plan_announce_reward_transaction,
        )
        self.user_plan1 = UserPlan.objects.create(
            user=self.user1,
            plan=self.plan,
            locked_amount=Decimal('1'),
            reward_amount=Decimal('54.0'),
            status=UserPlan.Status.RELEASED,
        )
        # user 2
        self.user2 = self.create_user()
        self.user2_stake_transaction = self.create_staking_transaction(
            user=self.user2,
            plan=self.plan,
            amount=Decimal('2'),
            tp=StakingTransaction.TYPES.stake,
        )
        self.user2_reward_transaction = self.create_staking_transaction(
            user=self.user2,
            plan=self.plan,
            amount=Decimal('54.0'),
            tp=StakingTransaction.TYPES.announce_reward,
            plan_transaction=self.plan_announce_reward_transaction,
        )
        self.user_plan2 = UserPlan.objects.create(
            user=self.user2,
            plan=self.plan,
            locked_amount=Decimal('2'),
            reward_amount=Decimal('54.0'),
            status=UserPlan.Status.EXTEND_TO_NEXT_CYCLE,
        )

        Settings.set(StakingFeatureFlags.CRONJOB_DUAL_WRITE, 'yes')

    @staticmethod
    def assert_transaction_amount(transaction: Union[PlanTransaction, StakingTransaction], amount: Decimal):
        transaction.refresh_from_db(fields=['amount'])
        assert transaction.amount == amount

    @staticmethod
    def assert_user_plan_reward_amount(user_plan: UserPlan, amount: Decimal):
        user_plan.refresh_from_db(fields=['reward_amount'])
        assert user_plan.reward_amount == amount

    def test_when_dual_write_flag_is_disabled_then_only_old_model_instances_update(self):
        Settings.set(StakingFeatureFlags.CRONJOB_DUAL_WRITE, 'no')

        edit_last_announced_reward(self.plan.id, Decimal('0.8'))

        self.assert_transaction_amount(self.plan_announce_reward_transaction, Decimal('0.8'))
        self.assert_transaction_amount(self.user1_reward_transaction, Decimal('0.08'))
        self.assert_transaction_amount(self.user2_reward_transaction, Decimal('0.16'))
        self.assert_user_plan_reward_amount(self.user_plan1, Decimal('54.0'))
        self.assert_user_plan_reward_amount(self.user_plan2, Decimal('54.0'))

    @patch('exchange.staking.service.announce_reward.Settings.get_flag')
    def test_when_edit_user_plan_function_raises_unknown_error_then_only_old_model_instances_update(
        self, mocked_internal_edit_user_plan
    ):
        mocked_internal_edit_user_plan.side_effect = Exception

        edit_last_announced_reward(self.plan.id, Decimal('0.8'))

        self.assert_transaction_amount(self.plan_announce_reward_transaction, Decimal('0.8'))
        self.assert_transaction_amount(self.user1_reward_transaction, Decimal('0.08'))
        self.assert_transaction_amount(self.user2_reward_transaction, Decimal('0.16'))
        self.assert_user_plan_reward_amount(self.user_plan1, Decimal('54.0'))
        self.assert_user_plan_reward_amount(self.user_plan2, Decimal('54.0'))

    def test_success_when_new_reward_amount_is_greater_than_zero(self):
        edit_last_announced_reward(self.plan.id, Decimal('0.8'))

        self.assert_transaction_amount(self.plan_announce_reward_transaction, Decimal('0.8'))
        self.assert_transaction_amount(self.user1_reward_transaction, Decimal('0.08'))
        self.assert_transaction_amount(self.user2_reward_transaction, Decimal('0.16'))
        self.assert_user_plan_reward_amount(self.user_plan1, Decimal('0.08'))
        self.assert_user_plan_reward_amount(self.user_plan2, Decimal('0.16'))

    def test_success_when_new_reward_amount_is_zero_then_users_reward_becomes_zero(self):
        edit_last_announced_reward(self.plan.id, Decimal('0.0'))

        self.assert_transaction_amount(self.plan_announce_reward_transaction, Decimal('0.00'))
        self.assert_transaction_amount(self.user1_reward_transaction, Decimal('0.00'))
        self.assert_transaction_amount(self.user2_reward_transaction, Decimal('0.00'))
        self.assert_user_plan_reward_amount(self.user_plan1, Decimal('0.00'))
        self.assert_user_plan_reward_amount(self.user_plan2, Decimal('0.00'))

    def test_when_plan_id_does_not_exist_then_error_is_raised(self):
        plan_id = Plan.objects.latest('id').id + 10

        with pytest.raises(InvalidPlanId):
            edit_last_announced_reward(plan_id, Decimal('0.8'))

        assert PlanTransaction.objects.filter(plan_id=plan_id).exists() is False
        assert UserPlan.objects.filter(plan_id=plan_id).exists() is False

    def test_when_plan_has_no_announce_reward_transaction_then_error_is_raised(self):
        plan = self.create_plan(**self.get_plan_kwargs())

        with pytest.raises(PlanTransaction.DoesNotExist):
            edit_last_announced_reward(plan.id, Decimal('0.8'))

        assert PlanTransaction.objects.filter(plan=plan).exists() is False
        assert UserPlan.objects.filter(plan=plan).exists() is False

    def test_when_user_has_no_user_plan_then_only_old_instances_update(self):
        self.user_plan1.delete()
        self.user_plan2.delete()

        edit_last_announced_reward(self.plan.id, Decimal('0.8'))

        self.assert_transaction_amount(self.plan_announce_reward_transaction, Decimal('0.8'))
        self.assert_transaction_amount(self.user1_reward_transaction, Decimal('0.08'))
        self.assert_transaction_amount(self.user2_reward_transaction, Decimal('0.16'))
        assert UserPlan.objects.filter(plan=self.plan).exists() is False

    def test_when_user_plan_is_in_rejected_status_then_no_update_happens_on_it(self):
        self.user_plan1.status = UserPlan.Status.ADMIN_REJECTED
        self.user_plan1.save(update_fields=['status'])

        edit_last_announced_reward(self.plan.id, Decimal('0.8'))

        self.assert_transaction_amount(self.plan_announce_reward_transaction, Decimal('0.8'))
        self.assert_transaction_amount(self.user1_reward_transaction, Decimal('0.08'))
        self.assert_transaction_amount(self.user2_reward_transaction, Decimal('0.16'))
        self.assert_user_plan_reward_amount(self.user_plan2, Decimal('0.16'))

        self.assert_user_plan_reward_amount(self.user_plan1, Decimal('54.00'))

    def test_when_user_plan_is_in_canceled_status_then_no_update_happens_on_it(self):
        self.user_plan1.status = UserPlan.Status.USER_CANCELED
        self.user_plan1.save(update_fields=['status'])

        edit_last_announced_reward(self.plan.id, Decimal('0.8'))

        self.assert_transaction_amount(self.plan_announce_reward_transaction, Decimal('0.8'))
        self.assert_transaction_amount(self.user1_reward_transaction, Decimal('0.08'))
        self.assert_transaction_amount(self.user2_reward_transaction, Decimal('0.16'))
        self.assert_user_plan_reward_amount(self.user_plan2, Decimal('0.16'))

        self.assert_user_plan_reward_amount(self.user_plan1, Decimal('54.00'))

    def test_when_user_plan_is_in_requested_status_then_no_update_happens_on_it(self):
        self.user_plan1.status = UserPlan.Status.REQUESTED
        self.user_plan1.save(update_fields=['status'])

        edit_last_announced_reward(self.plan.id, Decimal('0.8'))

        self.assert_transaction_amount(self.plan_announce_reward_transaction, Decimal('0.8'))
        self.assert_transaction_amount(self.user1_reward_transaction, Decimal('0.08'))
        self.assert_transaction_amount(self.user2_reward_transaction, Decimal('0.16'))
        self.assert_user_plan_reward_amount(self.user_plan2, Decimal('0.16'))

        self.assert_user_plan_reward_amount(self.user_plan1, Decimal('54.00'))
