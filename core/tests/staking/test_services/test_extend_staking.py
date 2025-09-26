from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import TestCase

from exchange.base.models import Settings
from exchange.staking.errors import (
    AdminMistake,
    InvalidPlanId,
    ParentIsNotCreated,
    PlanTransactionIsNotCreated,
    UserStakingAlreadyExtended,
)
from exchange.staking.helpers import StakingFeatureFlags
from exchange.staking.models import Plan, PlanTransaction, StakingTransaction, UserPlan
from exchange.staking.service.extend_staking import _extend_user_staking, extend_all_users_staking
from tests.staking.utils import StakingTestDataMixin


class ExtendStakingServiceTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = self.create_user()
        # user choose to extend all the assets to the next plan
        self.user_stake_transaction = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake, user=self.user, plan=self.plan, amount=Decimal('51')
        )
        self.user_extend_out_transaction = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.extend_out,
            user=self.user,
            plan=self.plan,
            amount=Decimal('51'),
            parent=self.user_stake_transaction,
        )
        # create extension plan
        self.extension_plan = self.create_plan(**self.get_plan_kwargs())
        self.extension_plan.extended_from = self.plan
        self.extension_plan.save()
        self.extension_plan_extend_in_transaction = self.create_plan_transaction(
            tp=PlanTransaction.TYPES.extend_in, plan=self.extension_plan
        )
        self.extension_plan_stake_transaction = self.create_plan_transaction(
            tp=PlanTransaction.TYPES.stake, plan=self.extension_plan, amount=Decimal('300')
        )

    def test_extend_user_staking_successfully(self):
        _extend_user_staking(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.extension_plan,
            tp=StakingTransaction.TYPES.extend_in,
            plan_transaction=self.extension_plan_extend_in_transaction,
            amount=Decimal('51'),
            parent=self.user_extend_out_transaction,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.extension_plan,
            tp=StakingTransaction.TYPES.stake,
            amount=Decimal('51'),
        )
        assert PlanTransaction.objects.get(
            plan=self.extension_plan,
            amount=Decimal('249'),
            tp=StakingTransaction.TYPES.stake,
        )

    def test_extend_user_plan_successfully_when_next_plan_does_not_have_stake_transaction(self):
        self.extension_plan_stake_transaction.delete()

        _extend_user_staking(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.extension_plan,
            tp=StakingTransaction.TYPES.extend_in,
            plan_transaction=self.extension_plan_extend_in_transaction,
            amount=Decimal('51'),
            parent=self.user_extend_out_transaction,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.extension_plan,
            tp=StakingTransaction.TYPES.stake,
            amount=Decimal('51'),
        )
        assert PlanTransaction.objects.get(
            plan=self.extension_plan,
            amount=-Decimal('51'),
            tp=StakingTransaction.TYPES.stake,
        )

    def test_extend_user_plan_successfully_when_user_already_has_stake_transaction_in_next_plan(self):
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake,
            user=self.user,
            plan=self.extension_plan,
            amount=Decimal('12'),
        )

        _extend_user_staking(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.extension_plan,
            tp=StakingTransaction.TYPES.extend_in,
            plan_transaction=self.extension_plan_extend_in_transaction,
            amount=Decimal('51'),
            parent=self.user_extend_out_transaction,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.extension_plan,
            tp=StakingTransaction.TYPES.stake,
            amount=Decimal('51') + Decimal('12'),
        )
        assert PlanTransaction.objects.get(
            plan=self.extension_plan,
            amount=Decimal('249'),
            tp=StakingTransaction.TYPES.stake,
        )

    def test_when_next_plan_has_no_extend_in_transaction_yet_then_error_is_raised(self):
        self.extension_plan_extend_in_transaction.delete()

        with pytest.raises(PlanTransactionIsNotCreated):
            _extend_user_staking(self.user.id, self.plan.id)

        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.extension_plan,
                tp=StakingTransaction.TYPES.extend_in,
            ).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user, plan=self.extension_plan, tp=StakingTransaction.TYPES.stake
            ).exists()
            == False
        )
        assert PlanTransaction.objects.get(
            plan=self.extension_plan,
            amount=Decimal('300'),
            tp=StakingTransaction.TYPES.stake,
        )

    def test_when_user_staking_is_already_extended_then_error_is_raised(self):
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.extend_in,
            user=self.user,
            plan=self.extension_plan,
            amount=Decimal('51'),
            parent=self.user_extend_out_transaction,
        )

        with pytest.raises(UserStakingAlreadyExtended):
            _extend_user_staking(self.user.id, self.plan.id)

        assert PlanTransaction.objects.get(
            plan=self.extension_plan,
            amount=Decimal('300'),
            tp=StakingTransaction.TYPES.stake,
        )

    def test_when_user_has_no_extend_out_transaction_then_error_is_raised(self):
        self.user_extend_out_transaction.delete()

        with pytest.raises(ParentIsNotCreated):
            _extend_user_staking(self.user.id, self.plan.id)

        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.extension_plan,
                tp=StakingTransaction.TYPES.extend_in,
            ).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user, plan=self.extension_plan, tp=StakingTransaction.TYPES.stake
            ).exists()
            == False
        )
        assert PlanTransaction.objects.get(
            plan=self.extension_plan,
            amount=Decimal('300'),
            tp=StakingTransaction.TYPES.stake,
        )

    def test_when_plan_has_no_next_plan_then_error_is_raised(self):
        self.extension_plan.delete()

        with pytest.raises(AdminMistake):
            _extend_user_staking(self.user.id, self.plan.id)

        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                tp=StakingTransaction.TYPES.extend_in,
            ).exists()
            == False
        )

    def test_when_user_has_extend_out_transaction_with_zero_amount_then_no_extension_happens(self):
        self.user_extend_out_transaction.amount = 0
        self.user_extend_out_transaction.save()

        _extend_user_staking(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.deactivator,
            parent=self.user_extend_out_transaction,
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.extension_plan,
                tp=StakingTransaction.TYPES.extend_in,
            ).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user, plan=self.extension_plan, tp=StakingTransaction.TYPES.stake
            ).exists()
            == False
        )
        assert PlanTransaction.objects.get(
            plan=self.extension_plan,
            amount=Decimal('300'),
            tp=StakingTransaction.TYPES.stake,
        )

    def test_when_plan_does_not_exist_then_error_is_raised(self):
        plan_id = Plan.objects.latest('id').id + 1000

        with pytest.raises(ParentIsNotCreated):
            _extend_user_staking(self.user.id, plan_id)

        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.extension_plan,
                tp=StakingTransaction.TYPES.extend_in,
            ).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user, plan=self.extension_plan, tp=StakingTransaction.TYPES.stake
            ).exists()
            == False
        )
        assert PlanTransaction.objects.get(
            plan=self.extension_plan,
            amount=Decimal('300'),
            tp=StakingTransaction.TYPES.stake,
        )


class ExtendStakingServiceNewModelsTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = self.create_user()
        # user with extend out transaction -- showing that wants to extend all the assets
        self.user_stake_transaction = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake, user=self.user, plan=self.plan, amount=Decimal('79')
        )
        self.user_extend_out_transaction = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.extend_out,
            user=self.user,
            plan=self.plan,
            amount=Decimal('79'),
            parent=self.user_stake_transaction,
        )
        # create extension plan
        self.extension_plan = self.create_plan(**self.get_plan_kwargs())
        self.extension_plan.extended_from = self.plan
        self.extension_plan.save()
        self.extension_plan_extend_in_transaction = self.create_plan_transaction(
            tp=PlanTransaction.TYPES.extend_in, plan=self.extension_plan
        )
        self.extension_plan_stake_transaction = self.create_plan_transaction(
            tp=PlanTransaction.TYPES.stake, plan=self.extension_plan, amount=Decimal('450')
        )
        # user plan with extend to next cycle data
        self.user_plan = UserPlan.objects.create(
            user=self.user,
            plan=self.plan,
            locked_amount=Decimal('79'),
            extended_to_next_cycle_amount=Decimal('79'),
            status=UserPlan.Status.EXTEND_TO_NEXT_CYCLE,
        )

        Settings.set(StakingFeatureFlags.CRONJOB_DUAL_WRITE, 'yes')

    def assert_user_plan_instances_success(self, next_cycle_locked_amount: Decimal, next_cycle_status: UserPlan.Status):
        user_plan = UserPlan.objects.get(
            user=self.user,
            plan=self.plan,
            locked_amount=Decimal('79'),
            extended_to_next_cycle_amount=Decimal('79'),
            status=UserPlan.Status.EXTEND_TO_NEXT_CYCLE,
        )
        assert user_plan.next_cycle is not None

        next_cycle_user_plan = UserPlan.objects.get(user=self.user, plan=self.extension_plan)
        assert user_plan.next_cycle == next_cycle_user_plan
        assert next_cycle_user_plan.locked_amount == next_cycle_locked_amount
        assert next_cycle_user_plan.status == next_cycle_status
        assert next_cycle_user_plan.extended_from_previous_cycle_amount == Decimal('79')

    def assert_staking_transactions_success(self):
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.extension_plan,
            tp=StakingTransaction.TYPES.extend_in,
            plan_transaction=self.extension_plan_extend_in_transaction,
            amount=Decimal('79'),
            parent=self.user_extend_out_transaction,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.extension_plan,
            tp=StakingTransaction.TYPES.stake,
            amount=Decimal('79'),
        )
        assert PlanTransaction.objects.get(
            plan=self.extension_plan,
            amount=Decimal('371'),
            tp=StakingTransaction.TYPES.stake,
        )

    def test_extend_user_plan_successfully_creates_both_models_instances(self):
        extend_all_users_staking(self.plan.id)

        self.assert_user_plan_instances_success(
            next_cycle_locked_amount=Decimal('79'),
            next_cycle_status=UserPlan.Status.EXTEND_FROM_PREVIOUS_CYCLE,
        )
        self.assert_staking_transactions_success()

    def test_extend_user_plan_successfully_when_user_has_no_requests_in_next_plan(self):
        extend_all_users_staking(self.plan.id)

        self.assert_user_plan_instances_success(
            next_cycle_locked_amount=Decimal('79'),
            next_cycle_status=UserPlan.Status.EXTEND_FROM_PREVIOUS_CYCLE,
        )

    def test_extend_user_plan_successfully_when_user_already_has_requested_user_plan_in_next_plan(self):
        UserPlan.objects.create(
            user=self.user,
            plan=self.extension_plan,
            requested_amount=Decimal('7'),
            locked_amount=Decimal('7'),
            status=UserPlan.Status.REQUESTED,
        )

        extend_all_users_staking(self.plan.id)

        self.assert_user_plan_instances_success(
            next_cycle_locked_amount=Decimal('86'),
            next_cycle_status=UserPlan.Status.REQUESTED,
        )

    @patch('exchange.staking.errors.report_exception')
    def test_when_next_plan_has_no_extend_in_transaction_yet_then_error_is_raised(self, mocked_report_exception):
        self.extension_plan_extend_in_transaction.delete()

        extend_all_users_staking(self.plan.id)

        assert UserPlan.objects.filter(user=self.user, plan=self.extension_plan).exists() is False
        self.user_plan.refresh_from_db(fields=['next_cycle'])
        assert self.user_plan.next_cycle is None
        mocked_report_exception.assert_called_once()

    @patch('exchange.staking.errors.report_exception')
    def test_when_user_plan_is_already_extended_then_error_is_raised(self, mocked_report_exception):
        nex_user_plan = UserPlan.objects.create(
            user=self.user,
            plan=self.extension_plan,
            requested_amount=Decimal('0.0'),
            locked_amount=Decimal('8'),
            status=UserPlan.Status.EXTEND_FROM_PREVIOUS_CYCLE,
            extended_from_previous_cycle_amount=Decimal('8'),
        )
        self.user_plan.next_cycle = nex_user_plan
        self.user_plan.save()

        extend_all_users_staking(self.plan.id)

        mocked_report_exception.assert_called_once()
        assert UserPlan.objects.get(
            user=self.user,
            plan=self.extension_plan,
            requested_amount=Decimal('0.0'),
            locked_amount=Decimal('8'),
            status=UserPlan.Status.EXTEND_FROM_PREVIOUS_CYCLE,
            extended_from_previous_cycle_amount=Decimal('8'),
        )

    @patch('exchange.staking.errors.report_exception')
    def test_when_user_has_no_user_plan_then_error_is_raised(self, mocked_report_exception):
        plan = self.create_plan(**self.get_plan_kwargs())
        self.user_extend_out_transaction = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.extend_out,
            user=self.user,
            plan=plan,
            amount=Decimal('89'),
        )

        extend_all_users_staking(plan.id)

        assert UserPlan.objects.filter(user=self.user, plan=self.extension_plan).exists() is False
        assert UserPlan.objects.filter(user=self.user, plan=plan).exists() is False
        self.user_plan.refresh_from_db(fields=['next_cycle'])
        assert self.user_plan.next_cycle is None
        mocked_report_exception.assert_called_once()

    @patch('exchange.staking.errors.report_exception')
    def test_when_plan_has_no_next_plan_then_error_is_raised(self, mocked_report_exception):
        self.extension_plan.extended_from = None
        self.extension_plan.save(update_fields=['extended_from'])

        extend_all_users_staking(self.plan.id)

        assert UserPlan.objects.filter(user=self.user, plan=self.extension_plan).exists() is False
        self.user_plan.refresh_from_db(fields=['next_cycle'])
        assert self.user_plan.next_cycle is None
        mocked_report_exception.assert_called_once()

    @patch('exchange.staking.errors.report_exception')
    def test_when_user_plan_extended_with_zero_extended_to_next_cycle_amount_then_error_is_raised(
        self, mocked_report_exception
    ):
        self.user_plan.extended_to_next_cycle_amount = 0
        self.user_plan.save(update_fields=['extended_to_next_cycle_amount'])

        extend_all_users_staking(self.plan.id)

        assert UserPlan.objects.filter(user=self.user, plan=self.extension_plan).exists() is False
        self.user_plan.refresh_from_db(fields=['next_cycle'])
        assert self.user_plan.next_cycle is None
        mocked_report_exception.assert_called_once()

    @patch('exchange.staking.errors.report_exception')
    def test_when_user_plan_extended_with_negative_extended_to_next_cycle_amount_then_error_is_raised(
        self, mocked_report_exception
    ):
        self.user_plan.extended_to_next_cycle_amount = -10
        self.user_plan.save(update_fields=['extended_to_next_cycle_amount'])

        extend_all_users_staking(self.plan.id)

        assert UserPlan.objects.filter(user=self.user, plan=self.extension_plan).exists() is False
        self.user_plan.refresh_from_db(fields=['next_cycle'])
        assert self.user_plan.next_cycle is None
        mocked_report_exception.assert_called_once()

    @patch('exchange.staking.errors.report_exception')
    def test_when_plan_does_not_exist_then_nothing_happens(self, mocked_report_exception):
        plan_id = Plan.objects.latest('id').id + 1000

        extend_all_users_staking(plan_id)

        assert UserPlan.objects.filter(user=self.user, plan_id=plan_id).exists() is False
        mocked_report_exception.assert_not_called()

    @patch('exchange.staking.errors.report_exception')
    def test_when_user_plan_is_in_status_other_than_extended_to_next_cycle_then_error_is_raised(
        self, mocked_report_exception
    ):
        self.user_plan.status = UserPlan.Status.USER_CANCELED
        self.user_plan.save(update_fields=['status'])
        extend_all_users_staking(self.plan.id)

        self.user_plan.status = UserPlan.Status.REQUESTED
        self.user_plan.save(update_fields=['status'])
        extend_all_users_staking(self.plan.id)

        self.user_plan.status = UserPlan.Status.RELEASED
        self.user_plan.save(update_fields=['status'])
        extend_all_users_staking(self.plan.id)

        self.user_plan.status = UserPlan.Status.EXTEND_FROM_PREVIOUS_CYCLE
        self.user_plan.save(update_fields=['status'])
        extend_all_users_staking(self.plan.id)

        self.user_plan.status = UserPlan.Status.PENDING_RELEASE
        self.user_plan.save(update_fields=['status'])
        extend_all_users_staking(self.plan.id)

        self.user_plan.status = UserPlan.Status.LOCKED
        self.user_plan.save(update_fields=['status'])
        extend_all_users_staking(self.plan.id)

        self.user_plan.status = UserPlan.Status.ADMIN_REJECTED
        self.user_plan.save(update_fields=['status'])
        extend_all_users_staking(self.plan.id)

        assert UserPlan.objects.filter(user=self.user, plan=self.extension_plan).exists() is False
        self.user_plan.refresh_from_db(fields=['next_cycle'])
        assert self.user_plan.next_cycle is None
        mocked_report_exception.call_count == 7

    @patch('exchange.staking.errors.report_exception')
    def test_when_user_has_user_plan_in_next_plan_with_status_other_than_requested_then_error_is_raised(
        self, mocked_report_exception
    ):
        next_cycle = UserPlan.objects.create(
            user=self.user,
            plan=self.extension_plan,
            requested_amount=Decimal('17'),
            locked_amount=Decimal('17'),
            status=UserPlan.Status.LOCKED,
        )
        extend_all_users_staking(self.plan.id)

        next_cycle.status = UserPlan.Status.USER_CANCELED
        next_cycle.save(update_fields=['status'])
        extend_all_users_staking(self.plan.id)

        next_cycle.status = UserPlan.Status.RELEASED
        next_cycle.save(update_fields=['status'])
        extend_all_users_staking(self.plan.id)

        next_cycle.status = UserPlan.Status.EXTEND_FROM_PREVIOUS_CYCLE
        next_cycle.save(update_fields=['status'])
        extend_all_users_staking(self.plan.id)

        next_cycle.status = UserPlan.Status.PENDING_RELEASE
        next_cycle.save(update_fields=['status'])
        extend_all_users_staking(self.plan.id)

        next_cycle.status = UserPlan.Status.ADMIN_REJECTED
        next_cycle.save(update_fields=['status'])
        extend_all_users_staking(self.plan.id)

        self.user_plan.refresh_from_db(fields=['next_cycle'])
        assert self.user_plan.next_cycle is None
        mocked_report_exception.call_count == 6

    def test_when_dual_write_feature_flag_is_disabled_then_no_new_model_instance_is_updated(self):
        Settings.set(StakingFeatureFlags.CRONJOB_DUAL_WRITE, 'no')

        extend_all_users_staking(self.plan.id)

        assert UserPlan.objects.filter(user=self.user, plan=self.extension_plan).exists() is False
        self.user_plan.refresh_from_db(fields=['next_cycle'])
        assert self.user_plan.next_cycle is None
        self.assert_staking_transactions_success()

    @patch('exchange.staking.service.subscription.Settings.get_flag')
    @patch('exchange.staking.errors.report_exception')
    def test_when_extend_user_plan_function_raises_unknown_error_then_report_exception_is_called_and_old_models_update(
        self, report_exception_mock, extend_user_plan_internal_action_mock
    ):
        extend_user_plan_internal_action_mock.side_effect = Exception

        extend_all_users_staking(self.plan.id)

        report_exception_mock.assert_called_once()
        assert UserPlan.objects.filter(user=self.user, plan=self.extension_plan).exists() is False
        self.user_plan.refresh_from_db(fields=['next_cycle'])
        assert self.user_plan.next_cycle is None
        self.assert_staking_transactions_success()
