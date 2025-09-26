from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.models import Settings
from exchange.staking.errors import (
    AssetAlreadyStaked,
    ParentIsNotCreated,
    PlanTransactionIsNotCreated,
    SystemRejectedCreateRequest,
)
from exchange.staking.helpers import StakingFeatureFlags
from exchange.staking.models import Plan, PlanTransaction, StakingTransaction, UserPlan, UserPlanRequest
from exchange.staking.service.stake_assets import stake_all_users_assets, stake_user_assets
from tests.staking.utils import StakingTestDataMixin


class StakeAssetsServiceTest(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = self.create_user()
        self.plan_stake_transaction = self.create_plan_transaction(
            PlanTransaction.TYPES.stake, plan=self.plan, amount=Decimal('100')
        )

    def assert_transactions(
        self, plan_stake_amount: Decimal, user_stake_amount: Decimal, user_create_request: StakingTransaction
    ):
        self.plan_stake_transaction.refresh_from_db(fields=['amount'])
        assert self.plan_stake_transaction.amount == plan_stake_amount
        assert (
            StakingTransaction.objects.get(tp=StakingTransaction.TYPES.stake, user=self.user, plan=self.plan).amount
            == user_stake_amount
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.system_accepted_create,
            amount=user_create_request.amount,
            parent=user_create_request,
            created_at=self.plan_stake_transaction.created_at,
            plan_transaction=self.plan_stake_transaction,
        )

    def test_stake_user_assets_successfully(self):
        user_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.create_request,
            amount=Decimal('12.1'),
            user=self.user,
            plan=self.plan,
        )

        stake_user_assets(self.user.id, self.plan.id)

        self.assert_transactions(
            plan_stake_amount=Decimal('87.9'),
            user_stake_amount=Decimal('12.1'),
            user_create_request=user_request,
        )

    def test_stake_assets_successfully_when_user_has_extended_stake_amount_from_previous_plan(self):
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake,
            amount=Decimal('5.5'),
            user=self.user,
            plan=self.plan,
        )
        user_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.create_request,
            amount=Decimal('13.75'),
            user=self.user,
            plan=self.plan,
        )

        stake_user_assets(self.user.id, self.plan.id)

        self.assert_transactions(
            plan_stake_amount=Decimal('86.25'),
            user_stake_amount=Decimal('13.75') + Decimal('5.5'),
            user_create_request=user_request,
        )

    def test_stake_asset_when_already_staked_them_raises_error(self):
        user_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.create_request,
            amount=Decimal('11'),
            user=self.user,
            plan=self.plan,
        )
        self.create_staking_transaction(
            plan=self.plan,
            user=self.user,
            tp=StakingTransaction.TYPES.system_accepted_create,
            amount=Decimal('11'),
            parent=user_request,
        )
        StakingTransaction.objects.create(
            user_id=self.user.id,
            plan_id=self.plan.id,
            tp=StakingTransaction.TYPES.stake,
            amount=Decimal('11'),
        )
        with pytest.raises(AssetAlreadyStaked):
            stake_user_assets(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            tp=StakingTransaction.TYPES.stake, user=self.user, plan=self.plan
        ).amount == Decimal('11')

    def test_when_user_has_only_extended_amount_from_previous_plan_then_error_is_raised(self):
        StakingTransaction.objects.create(
            user_id=self.user.id,
            plan_id=self.plan.id,
            tp=StakingTransaction.TYPES.stake,
            amount=Decimal('13.1'),
        )
        with pytest.raises(AssetAlreadyStaked):
            stake_user_assets(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            tp=StakingTransaction.TYPES.stake, user=self.user, plan=self.plan
        ).amount == Decimal('13.1')

    def test_stake_asset_when_system_rejected_create_staking_request_then_raises_error(self):
        StakingTransaction.objects.create(
            user_id=self.user.id,
            plan_id=self.plan.id,
            tp=StakingTransaction.TYPES.system_rejected_create,
            amount=Decimal('20'),
        )
        with pytest.raises(SystemRejectedCreateRequest):
            stake_user_assets(self.user.id, self.plan.id)

        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.stake, user=self.user, plan=self.plan
            ).exists()
            is False
        )

    def test_stake_asset_when_user_has_no_create_request_then_raises_error(self):
        plan = self.create_plan(**self.get_plan_kwargs())
        with pytest.raises(ParentIsNotCreated):
            stake_user_assets(self.user.id, plan.id)

        assert (
            StakingTransaction.objects.filter(tp=StakingTransaction.TYPES.stake, user=self.user, plan=plan).exists()
            == False
        )

    def test_stake_asset_when_plan_has_no_stake_transaction_then_raises_error(self):
        plan = self.create_plan(**self.get_plan_kwargs())
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.create_request,
            amount=Decimal('13'),
            user=self.user,
            plan=plan,
        )
        with pytest.raises(PlanTransactionIsNotCreated):
            stake_user_assets(self.user.id, plan.id)

        assert (
            StakingTransaction.objects.filter(tp=StakingTransaction.TYPES.stake, user=self.user, plan=plan).exists()
            == False
        )


class StakeAllUsersAssetsTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user1 = self.create_user()
        self.user2 = self.create_user()
        self.user3 = self.create_user()

        # two new users
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.create_request, plan=self.plan, user=self.user1, amount=Decimal('12.78')
        )
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.create_request, plan=self.plan, user=self.user2, amount=Decimal('3')
        )

        # user3 with extension from previous plan
        self.user3_stake_transaction = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake, plan=self.plan, user=self.user3, amount=Decimal('2')
        )
        self.user3_create_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.create_request, plan=self.plan, user=self.user3, amount=Decimal('21')
        )

        self.plan_stake_transaction = self.create_plan_transaction(
            PlanTransaction.TYPES.stake, plan=self.plan, amount=Decimal('100')
        )

    def test_stake_all_assets_success_calls_stakes_all_plan_users_assets(self):
        stake_all_users_assets(self.plan.id)

        self.plan_stake_transaction.refresh_from_db(fields=['amount'])
        assert self.plan_stake_transaction.amount == Decimal('100') - Decimal('21') - Decimal('3') - Decimal('12.78')
        self.user3_stake_transaction.refresh_from_db(fields=['amount'])
        assert self.user3_stake_transaction.amount == Decimal('2') + Decimal('21')
        assert StakingTransaction.objects.get(
            user=self.user2,
            plan=self.plan,
            amount=Decimal('3'),
            tp=StakingTransaction.TYPES.stake,
        )
        assert StakingTransaction.objects.get(
            user=self.user1,
            plan=self.plan,
            amount=Decimal('12.78'),
            tp=StakingTransaction.TYPES.stake,
        )

    @patch('exchange.staking.service.stake_assets.report_event')
    def test_stake_assets_when_staking_more_than_plans_assets_then_overstaking_error_is_reported_and_all_create_requests_stake(
        self, mocked_report_event
    ):
        self.user3_create_request.amount = Decimal('150')
        self.user3_create_request.save()

        stake_all_users_assets(self.plan.id)

        self.plan_stake_transaction.refresh_from_db(fields=['amount'])
        self.user3_stake_transaction.refresh_from_db(fields=['amount'])
        assert self.plan_stake_transaction.amount == -Decimal('65.78')
        assert self.user3_stake_transaction.amount == Decimal('2') + Decimal('150')
        assert StakingTransaction.objects.get(
            user=self.user2,
            plan=self.plan,
            amount=Decimal('3'),
            tp=StakingTransaction.TYPES.stake,
        )
        assert StakingTransaction.objects.get(
            user=self.user1,
            plan=self.plan,
            amount=Decimal('12.78'),
            tp=StakingTransaction.TYPES.stake,
        )

        mocked_report_event.assert_called_once_with(
            message='UnexpectedError.OverStaking',
            level='error',
            tags={'module': 'staking'},
            extras={'plan_id': self.plan.id, 'amount': -Decimal('65.78')},
        )


class StakeAllAssetsNewModelsTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user1 = self.create_user()
        self.user2 = self.create_user()
        self.user3 = self.create_user()

        # new user
        self.user1_create_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.create_request,
            plan=self.plan,
            user=self.user1,
            amount=Decimal('9.7'),
        )
        self.user1_user_plan = UserPlan.objects.create(
            user=self.user1,
            plan=self.plan,
            requested_amount=Decimal('9.7'),
            locked_amount=Decimal('9.7'),
            status=UserPlan.Status.REQUESTED,
        )
        self.user1_subscription_request = UserPlanRequest.objects.create(
            user_plan=self.user1_user_plan,
            amount=Decimal('9.7'),
            tp=UserPlanRequest.Type.SUBSCRIPTION,
            status=UserPlanRequest.Status.CREATED,
        )

        # user2 with extension from previous plan
        self.user2_stake_transaction = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake, plan=self.plan, user=self.user2, amount=Decimal('2.5')
        )
        self.user2_user_plan = UserPlan.objects.create(
            user=self.user2,
            plan=self.plan,
            requested_amount=Decimal('0.0'),
            locked_amount=Decimal('2.5'),
            extended_from_previous_cycle_amount=Decimal('2.5'),
            status=UserPlan.Status.EXTEND_FROM_PREVIOUS_CYCLE,
        )

        # user3 extension from previous plan and a new request
        self.user3_create_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake, plan=self.plan, user=self.user3, amount=Decimal('31')
        )
        self.user3_stake_transaction = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.create_request,
            plan=self.plan,
            user=self.user3,
            amount=Decimal('6'),
        )
        self.user3_user_plan = UserPlan.objects.create(
            user=self.user3,
            plan=self.plan,
            requested_amount=Decimal('6'),
            locked_amount=Decimal('37'),
            extended_from_previous_cycle_amount=Decimal('31'),
            status=UserPlan.Status.EXTEND_FROM_PREVIOUS_CYCLE,
        )
        self.user3_subscription_request = UserPlanRequest.objects.create(
            user_plan=self.user3_user_plan,
            amount=Decimal('6'),
            tp=UserPlanRequest.Type.SUBSCRIPTION,
            status=UserPlanRequest.Status.CREATED,
        )

        self.plan_stake_transaction = self.create_plan_transaction(
            PlanTransaction.TYPES.stake, plan=self.plan, amount=Decimal('300')
        )

        Settings.get_flag(StakingFeatureFlags.CRONJOB_DUAL_WRITE, 'yes')

    def assert_staking_transaction(
        self, user: User, amount: Decimal, tp: int = StakingTransaction.TYPES.stake, plan: Plan = None
    ):
        plan = plan or self.plan
        assert StakingTransaction.objects.get(user=user, plan=plan, amount=amount, tp=tp)

    def assert_user_plan_instance(
        self,
        user: User,
        requested_amount: Decimal,
        locked_amount: Decimal,
        extended_amount: Decimal,
        plan: Plan = None,
    ):
        plan = plan or self.plan
        user_plan = UserPlan.objects.get(
            user=user,
            plan=plan,
            requested_amount=requested_amount,
            locked_amount=locked_amount,
            extended_from_previous_cycle_amount=extended_amount,
            status=UserPlan.Status.LOCKED,
        )
        assert user_plan.locked_at is not None

    def assert_user_request_accepted(self, amount: Decimal, user_plan: UserPlan):
        assert UserPlanRequest.objects.get(
            user_plan=user_plan,
            amount=amount,
            tp=UserPlanRequest.Type.SUBSCRIPTION,
            status=UserPlanRequest.Status.ACCEPTED,
        )

    def assert_user_plans_not_change(self):
        self.user1_user_plan.refresh_from_db(fields=['status', 'locked_at'])
        self.user1_subscription_request.refresh_from_db(fields=['status'])
        self.user2_user_plan.refresh_from_db(fields=['status', 'locked_at'])
        self.user3_user_plan.refresh_from_db(fields=['status', 'locked_at'])
        self.user3_subscription_request.refresh_from_db(fields=['status'])

        assert self.user1_user_plan.status == UserPlan.Status.REQUESTED
        assert self.user1_user_plan.locked_at is None
        assert self.user1_subscription_request.status == UserPlanRequest.Status.CREATED

        assert self.user2_user_plan.status == UserPlan.Status.EXTEND_FROM_PREVIOUS_CYCLE
        assert self.user2_user_plan.locked_at is None

        assert self.user3_user_plan.status == UserPlan.Status.EXTEND_FROM_PREVIOUS_CYCLE
        assert self.user3_user_plan.locked_at is None
        assert self.user3_subscription_request.status == UserPlanRequest.Status.CREATED

    def test_stake_all_assets_success_updates_both_models_instances(self):
        stake_all_users_assets(self.plan.id)

        self.assert_staking_transaction(user=self.user1, amount=Decimal('9.7'))
        self.assert_user_plan_instance(
            user=self.user1,
            requested_amount=Decimal('9.7'),
            locked_amount=Decimal('9.7'),
            extended_amount=Decimal('0'),
        )
        self.assert_user_request_accepted(user_plan=self.user1_user_plan, amount=Decimal('9.7'))

    def test_stake_all_assets_when_users_has_both_extended_plans_and_new_requested_plans(self):
        stake_all_users_assets(self.plan.id)

        self.assert_staking_transaction(user=self.user2, amount=Decimal('2.5'))
        self.assert_staking_transaction(user=self.user3, amount=Decimal('37'))
        self.assert_user_plan_instance(
            user=self.user2,
            requested_amount=Decimal('0.0'),
            locked_amount=Decimal('2.5'),
            extended_amount=Decimal('2.5'),
        )
        self.assert_user_plan_instance(
            user=self.user3,
            requested_amount=Decimal('6'),
            locked_amount=Decimal('37'),
            extended_amount=Decimal('31'),
        )
        self.assert_user_request_accepted(user_plan=self.user3_user_plan, amount=Decimal('6'))

    def test_when_user_plans_are_not_in_requested_or_extended_status_then_no_update_happens_on_them(self):
        user_plan1 = UserPlan.objects.create(
            user=self.create_user(),
            plan=self.plan,
            requested_amount=Decimal('1'),
            locked_amount=Decimal('1'),
            status=UserPlan.Status.RELEASED,
        )
        user_plan2 = UserPlan.objects.create(
            user=self.create_user(),
            plan=self.plan,
            requested_amount=Decimal('12'),
            locked_amount=Decimal('12'),
            status=UserPlan.Status.ADMIN_REJECTED,
        )
        user_plan3 = UserPlan.objects.create(
            user=self.create_user(),
            plan=self.plan,
            requested_amount=Decimal('13'),
            locked_amount=Decimal('13'),
            status=UserPlan.Status.USER_CANCELED,
        )
        user_plan4 = UserPlan.objects.create(
            user=self.create_user(),
            plan=self.plan,
            requested_amount=Decimal('15'),
            locked_amount=Decimal('15'),
            status=UserPlan.Status.EXTEND_TO_NEXT_CYCLE,
        )

        stake_all_users_assets(self.plan.id)

        user_plan1.refresh_from_db(fields=['status'])
        user_plan2.refresh_from_db(fields=['status'])
        user_plan3.refresh_from_db(fields=['status'])
        user_plan4.refresh_from_db(fields=['status'])
        assert user_plan1.status == UserPlan.Status.RELEASED
        assert user_plan2.status == UserPlan.Status.ADMIN_REJECTED
        assert user_plan3.status == UserPlan.Status.USER_CANCELED
        assert user_plan4.status == UserPlan.Status.EXTEND_TO_NEXT_CYCLE

    def test_when_dual_write_flag_is_disabled_then_no_new_model_instances_change(self):
        Settings.set(StakingFeatureFlags.CRONJOB_DUAL_WRITE, 'no')

        stake_all_users_assets(self.plan.id)

        self.assert_staking_transaction(user=self.user1, amount=Decimal('9.7'))
        self.assert_staking_transaction(user=self.user2, amount=Decimal('2.5'))
        self.assert_staking_transaction(user=self.user3, amount=Decimal('37'))
        self.assert_user_plans_not_change()

    @patch('exchange.staking.service.subscription.Settings.get_flag')
    @patch('exchange.staking.errors.report_exception')
    def test_when_lock_user_plan_raises_unknown_error_then_only_new_model_instances_change(
        self, mocked_report_exception, mocked_inner_lock_user_plan
    ):
        mocked_inner_lock_user_plan.side_effect = Exception

        stake_all_users_assets(self.plan.id)

        self.assert_staking_transaction(user=self.user1, amount=Decimal('9.7'))
        self.assert_staking_transaction(user=self.user2, amount=Decimal('2.5'))
        self.assert_staking_transaction(user=self.user3, amount=Decimal('37'))
        self.assert_user_plans_not_change()
        mocked_report_exception.assert_called_once()

    @patch('exchange.staking.admin_notifier.notify_or_raise_exception')
    @patch('exchange.staking.errors.report_exception')
    def test_stake_asset_when_plan_has_no_active_stake_transaction_then_raises_error_and_no_instance_is_updated(
        self, mocked_user_plan_report_exception, mocked_stake_assets_report_exception
    ):
        self.create_plan_transaction(
            parent_transaction=self.plan_stake_transaction,
            tp=PlanTransaction.TYPES.extend_out,
            plan=self.plan,
            amount=Decimal('98'),
        )

        stake_all_users_assets(self.plan.id)

        assert mocked_user_plan_report_exception.call_count == 1
        assert mocked_stake_assets_report_exception.call_count == 3
        self.assert_user_plans_not_change()
        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.stake, user=self.user1, plan=self.plan
            ).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.stake, user=self.user3, plan=self.plan, amount=Decimal('37')
            ).exists()
            == False
        )

    def test_plan_stake_transaction_is_reduced_for_each_new_request(self):
        stake_all_users_assets(self.plan.id)

        amount = (
            self.plan_stake_transaction.amount
            - self.user1_subscription_request.amount
            - self.user3_subscription_request.amount
        )
        assert PlanTransaction.objects.get(
            plan=self.plan,
            amount=amount,
            tp=PlanTransaction.TYPES.stake,
        )

    @patch('exchange.staking.service.stake_assets.report_event')
    def test_when_staking_more_than_plans_assets_then_overstaking_error_is_reported_and_all_create_requests_accepted(
        self, mocked_report_event
    ):
        self.user1_create_request.amount = Decimal('400.0')
        self.user1_subscription_request.amount = Decimal('400.0')
        self.user1_user_plan.locked_amount = Decimal('400.0')
        self.user1_user_plan.requested_amount = Decimal('400.0')
        self.user1_create_request.save()
        self.user1_subscription_request.save()
        self.user1_user_plan.save()

        stake_all_users_assets(self.plan.id)

        self.assert_staking_transaction(user=self.user1, amount=Decimal('400.0'))
        self.assert_user_plan_instance(
            user=self.user1,
            requested_amount=Decimal('400.0'),
            locked_amount=Decimal('400.0'),
            extended_amount=Decimal('0'),
        )
        self.assert_user_request_accepted(user_plan=self.user1_user_plan, amount=Decimal('400.0'))

        assert PlanTransaction.objects.get(plan=self.plan, tp=PlanTransaction.TYPES.stake).amount == -Decimal('106')
        mocked_report_event.assert_called_once_with(
            message='UnexpectedError.OverStaking',
            level='error',
            tags={'module': 'staking'},
            extras={'plan_id': self.plan.id, 'amount': -Decimal('106')},
        )
