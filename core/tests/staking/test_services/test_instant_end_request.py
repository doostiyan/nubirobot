from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from exchange.staking.errors import CantEndReleasedStaking, InvalidAmount, InvalidPlanId, PlanIsNotInstantlyUnstakable
from exchange.staking.helpers import StakingFeatureFlags
from exchange.staking.models import Plan, StakingTransaction, UserPlan, UserPlanRequest
from exchange.staking.service.instant_end import (
    _apply_instant_end_request,
    _create_instant_end_request,
    add_and_apply_instant_end_request,
)
from tests.staking.utils import StakingTestDataMixin


class CreateInstantEndTest(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = User.objects.get(id=202)
        self.user_stake_transaction = self.create_staking_transaction(
            StakingTransaction.TYPES.stake, Decimal('25'), plan=self.plan, user=self.user
        )

    def assert_instant_end_transactions(
        self,
        amount: Decimal,
        parent: StakingTransaction = None,
        tp: int = StakingTransaction.TYPES.instant_end_request,
    ):
        assert StakingTransaction.objects.get(
            user_id=self.user.id,
            plan_id=self.plan.id,
            parent=parent,
            tp=tp,
            amount=amount,
        )

    def test_create_instant_end_request_successfully(self):
        _create_instant_end_request(self.user.id, self.plan.id, Decimal('2.5'))

        self.assert_instant_end_transactions(amount=Decimal('2.5'))

    def test_create_instant_end_request_when_user_has_active_instant_end_transaction_then_amount_is_summed(self):
        parent_instant_end = _create_instant_end_request(self.user.id, self.plan.id, Decimal('2.5'))
        self.assert_instant_end_transactions(amount=Decimal('2.5'))

        _create_instant_end_request(self.user.id, self.plan.id, Decimal('3.1'))
        self.assert_instant_end_transactions(amount=Decimal(' 5.6'), parent=parent_instant_end)

    def test_when_plan_is_not_instantly_unstakable_then_error_is_raised(self):
        self.plan.is_instantly_unstakable = False
        self.plan.save(update_fields=['is_instantly_unstakable'])
        with pytest.raises(PlanIsNotInstantlyUnstakable):
            _create_instant_end_request(self.user.id, self.plan.id, Decimal('3.4'))

        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.instant_end_request, user=self.user, plan=self.plan, amount=Decimal('3.4')
            ).exists()
            is False
        )

    def test_when_requested_amount_is_less_than_zero_then_error_is_raised(self):
        with pytest.raises(InvalidAmount) as e:
            _create_instant_end_request(self.user.id, self.plan.id, Decimal('-12'))

        assert e.value.message == 'Amount is too low.'
        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.instant_end_request, user=self.user, plan=self.plan
            ).exists()
            is False
        )

    def test_when_total_stake_amount_becomes_less_than_plan_min_staking_amount_then_error_is_raised(self):
        self.plan.min_staking_amount = 10
        self.plan.save(update_fields=['min_staking_amount'])

        with pytest.raises(InvalidAmount) as e:
            _create_instant_end_request(self.user.id, self.plan.id, Decimal('15.1'))

        assert e.value.message == f"Amount is not acceptable. (plan_id: '{self.plan.id}')"
        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.instant_end_request, user=self.user, plan=self.plan
            ).exists()
            is False
        )

    def test_when_user_has_active_request_then_second_request_amount_reduces_total_stake_amount_less_than_plan_min_staking(
        self,
    ):
        self.plan.min_staking_amount = 10
        self.plan.save(update_fields=['min_staking_amount'])

        parent_instant_end = _create_instant_end_request(self.user.id, self.plan.id, Decimal('2.5'))
        self.assert_instant_end_transactions(amount=Decimal('2.5'))

        with pytest.raises(InvalidAmount) as e:
            _create_instant_end_request(self.user.id, self.plan.id, Decimal('12.6'))
        assert e.value.message == f"Amount is not acceptable. (plan_id: '{self.plan.id}')"
        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.instant_end_request,
                user=self.user,
                plan=self.plan,
                parent=parent_instant_end,
            ).exists()
            is False
        )
        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.instant_end_request, user=self.user, plan=self.plan
            ).count()
            == 1
        )

    def test_when_user_has_no_staking_in_plan_then_error_is_raised(self):
        plan = self.create_plan(**self.get_plan_kwargs())

        with pytest.raises(InvalidPlanId):
            _create_instant_end_request(self.user.id, plan.id, Decimal('3.5'))
        assert StakingTransaction.objects.filter(user=self.user, plan=plan).exists() is False

    def test_when_plan_is_ended_then_error_is_raised(self):
        self.plan.staked_at = ir_now() - self.plan.staking_period
        self.plan.save(update_fields=['staked_at'])

        with pytest.raises(CantEndReleasedStaking):
            _create_instant_end_request(self.user.id, self.plan.id, Decimal('5.5'))

        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.instant_end_request, user=self.user, plan=self.plan
            ).exists()
            is False
        )

    def test_when_plan_id_does_not_exist_then_error_is_raised(self):
        plan_id = Plan.objects.latest('id').id + 10
        with pytest.raises(InvalidPlanId):
            _create_instant_end_request(self.user.id, plan_id, Decimal('3.5'))
        assert StakingTransaction.objects.filter(user=self.user, plan_id=plan_id).exists() is False


class ApplyInstantEndRequest(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.plan.total_capacity = Decimal('100000')
        self.plan.filled_capacity = Decimal('100')
        self.plan.save(update_fields=('total_capacity', 'filled_capacity'))
        self.user = User.objects.get(id=202)
        self.user_stake_transaction = self.create_staking_transaction(
            StakingTransaction.TYPES.stake, Decimal('25'), plan=self.plan, user=self.user
        )
        self.instant_end_request = self.create_staking_transaction(
            StakingTransaction.TYPES.instant_end_request, Decimal('5'), plan=self.plan, user=self.user
        )

    def assert_apply_end_request_success(self):
        self.plan.refresh_from_db(fields=['filled_capacity'])
        self.user_stake_transaction.refresh_from_db(fields=['amount'])
        assert self.user_stake_transaction.amount == Decimal('20')
        assert self.plan.filled_capacity == Decimal('95')
        assert StakingTransaction.objects.get(
            plan=self.plan,
            user=self.user,
            tp=StakingTransaction.TYPES.unstake,
            amount=self.instant_end_request.amount,
            parent=self.instant_end_request,
        )

    def test_apply_instant_end_request_successfully(self):
        _apply_instant_end_request(self.user.id, self.plan.id)

        self.assert_apply_end_request_success()

    def test_apply_instant_end_request_successfully_when_user_has_reward_transaction(self):
        reward_transaction = self.create_staking_transaction(
            StakingTransaction.TYPES.announce_reward, Decimal('3.230'), plan=self.plan, user=self.user
        )
        _apply_instant_end_request(self.user.id, self.plan.id)

        self.assert_apply_end_request_success()
        reward_transaction.refresh_from_db(fields=['amount'])
        assert reward_transaction.amount == Decimal('2.5840')


class AddAndApplyInstantEndRequestTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = self.create_user()
        self.plan.total_capacity = Decimal('100000')
        self.plan.filled_capacity = Decimal('110.5')
        self.plan.save(update_fields=('total_capacity', 'filled_capacity'))
        self.user_stake_transaction = self.create_staking_transaction(
            StakingTransaction.TYPES.stake, Decimal('101'), plan=self.plan, user=self.user
        )

    @patch('exchange.staking.service.instant_end.add_user_plan_early_end_request')
    def test_call_add_and_apply_instant_end_successfully_then_adds_both_instant_end_and_unstake_transactions_and_updates_plan_capacity(
        self, mock_new_schema
    ):
        mock_new_schema.return_value = None

        add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('3.5'))
        instant_end_transaction = StakingTransaction.objects.get(
            user_id=self.user.id,
            plan_id=self.plan.id,
            parent=None,
            tp=StakingTransaction.TYPES.instant_end_request,
            amount=Decimal('3.5'),
        )
        self.plan.refresh_from_db(fields=['filled_capacity'])
        self.user_stake_transaction.refresh_from_db(fields=['amount'])
        assert self.user_stake_transaction.amount == Decimal('97.5')
        assert self.plan.filled_capacity == Decimal('107')
        assert StakingTransaction.objects.get(
            plan=self.plan,
            user=self.user,
            tp=StakingTransaction.TYPES.unstake,
            amount=instant_end_transaction.amount,
            parent=instant_end_transaction,
        )


class AddAndApplyInstantEndRequestNewModelsTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = self.create_user()
        self.plan.total_capacity = Decimal('100000')
        self.plan.filled_capacity = Decimal('2001.5')
        self.plan.save(update_fields=('total_capacity', 'filled_capacity'))
        self.user_stake_transaction = self.create_staking_transaction(
            StakingTransaction.TYPES.stake,
            Decimal('127.0'),
            plan=self.plan,
            user=self.user,
        )
        self.user_plan = UserPlan.objects.create(
            user=self.user,
            plan=self.plan,
            requested_amount=Decimal('127.0'),
            locked_amount=Decimal('127.0'),
            early_ended_amount=Decimal('0.0'),
            status=UserPlan.Status.LOCKED,
        )

        Settings.set(StakingFeatureFlags.API_DUAL_WRITE, value='yes')

    def assert_staking_transactions(
        self,
        instant_end_amount: Decimal,
        stake_amount: Decimal,
        plan: Plan = None,
        user_stake_transaction: StakingTransaction = None,
    ):
        plan = plan or self.plan
        user_stake_transaction = user_stake_transaction or self.user_stake_transaction
        instant_end_request = StakingTransaction.objects.get(
            user_id=self.user.id,
            plan_id=plan.id,
            tp=StakingTransaction.TYPES.instant_end_request,
            amount=instant_end_amount,
        )
        assert StakingTransaction.objects.get(
            user_id=self.user.id,
            plan_id=plan.id,
            parent=instant_end_request,
            tp=StakingTransaction.TYPES.unstake,
            amount=instant_end_request.amount,
        )
        user_stake_transaction.refresh_from_db(fields=['amount'])
        assert user_stake_transaction.amount == stake_amount

    def assert_plan_filled_capacity(self, plan_filled_capacity: Decimal):
        self.plan.refresh_from_db(fields=['filled_capacity'])
        assert self.plan.filled_capacity == plan_filled_capacity

    def assert_user_plan_instances(
        self,
        locked_amount: Decimal,
        early_end_amount: Decimal,
        early_end_request_amount: Decimal,
        status=UserPlan.Status.LOCKED,
        created_by_admin=False,
    ):
        self.user_plan.refresh_from_db()
        assert self.user_plan.locked_amount == locked_amount
        assert self.user_plan.early_ended_amount == early_end_amount
        assert self.user_plan.status == status
        assert (
            self.user_plan.locked_amount + self.user_plan.early_ended_amount
            == self.user_plan.requested_amount - self.user_plan.admin_rejected_amount
        )
        assert UserPlanRequest.objects.get(
            amount=early_end_request_amount,
            user_plan=self.user_plan,
            tp=UserPlanRequest.Type.EARLY_END,
            status=UserPlanRequest.Status.CREATED,
            created_by_admin=created_by_admin,
        )

    def test_when_staking_dual_write_flag_is_disabled_then_no_new_models_instances_are_created(self):
        Settings.set(StakingFeatureFlags.API_DUAL_WRITE, value='no')
        add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('27'))

        self.assert_staking_transactions(instant_end_amount=Decimal('27'), stake_amount=Decimal('100'))
        self.assert_plan_filled_capacity(
            plan_filled_capacity=Decimal('1974.5'),
        )
        assert UserPlanRequest.objects.filter(user_plan=self.user_plan).exists() is False

    @patch('exchange.staking.service.subscription.Settings.get_flag')
    @patch('exchange.staking.errors.report_exception')
    def test_when_raises_unknown_error_then_then_no_new_models_instances_are_created_and_report_exception_is_called(
        self, mocked_report_exception, mocked_inner_add_user_plan
    ):
        mocked_inner_add_user_plan.side_effect = Exception
        add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('28'))

        self.assert_staking_transactions(instant_end_amount=Decimal('28'), stake_amount=Decimal('99'))
        self.assert_plan_filled_capacity(
            plan_filled_capacity=Decimal('1973.5'),
        )
        assert UserPlanRequest.objects.filter(user_plan=self.user_plan).exists() is False
        mocked_report_exception.assert_called_once()

    def test_add_instant_request_successfully_adds_both_new_schema_and_old_schema_instances(self):
        add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('6.5'))

        self.assert_staking_transactions(instant_end_amount=Decimal('6.5'), stake_amount=Decimal('120.5'))
        self.assert_plan_filled_capacity(
            plan_filled_capacity=Decimal('1995.0'),
        )
        self.assert_user_plan_instances(
            locked_amount=Decimal('120.5'),
            early_end_amount=Decimal('6.5'),
            early_end_request_amount=Decimal('6.5'),
        )

    def test_add_instant_request_successfully_by_admins_sets_admin_flag(self):
        add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('6.5'), created_by_admin=True)

        self.assert_staking_transactions(instant_end_amount=Decimal('6.5'), stake_amount=Decimal('120.5'))
        self.assert_plan_filled_capacity(
            plan_filled_capacity=Decimal('1995.0'),
        )
        self.assert_user_plan_instances(
            locked_amount=Decimal('120.5'),
            early_end_amount=Decimal('6.5'),
            early_end_request_amount=Decimal('6.5'),
            created_by_admin=True,
        )

    def test_create_instant_end_request_multiple_times_adds_both_new_schema_and_old_schema_instances(self):
        add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('7.5'))
        self.assert_staking_transactions(instant_end_amount=Decimal('7.5'), stake_amount=Decimal('119.5'))
        self.assert_plan_filled_capacity(
            plan_filled_capacity=Decimal('1994.0'),
        )
        self.assert_user_plan_instances(
            locked_amount=Decimal('119.5'),
            early_end_amount=Decimal('7.5'),
            early_end_request_amount=Decimal('7.5'),
        )

        add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('2.1'))
        self.assert_staking_transactions(instant_end_amount=Decimal('2.1'), stake_amount=Decimal('117.4'))
        self.assert_plan_filled_capacity(
            plan_filled_capacity=Decimal('1991.9'),
        )
        self.assert_user_plan_instances(
            locked_amount=Decimal('117.4'),
            early_end_amount=Decimal('7.5') + Decimal('2.1'),
            early_end_request_amount=Decimal('2.1'),
        )

    def test_when_user_instantly_ends_all_locked_amount_then_user_plan_status_changes_to_released(self):
        add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('127.0'))

        self.assert_staking_transactions(instant_end_amount=Decimal('127.0'), stake_amount=Decimal('0.0'))
        self.assert_plan_filled_capacity(
            plan_filled_capacity=Decimal('1874.5'),
        )
        self.assert_user_plan_instances(
            locked_amount=Decimal('0.0'),
            early_end_amount=Decimal('127.0'),
            early_end_request_amount=Decimal('127.0'),
            status=UserPlan.Status.RELEASED,
        )

    def test_when_user_instantly_ends_all_locked_amount_in_multiple_requests_then_user_plan_status_changes_to_released(
        self,
    ):
        add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('100.0'))
        add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('19.0'))
        add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('1.80'))
        add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('6.20'))

        self.assert_plan_filled_capacity(
            plan_filled_capacity=Decimal('1874.5'),
        )
        self.assert_user_plan_instances(
            locked_amount=Decimal('0.0'),
            early_end_amount=Decimal('127.0'),
            early_end_request_amount=Decimal('6.20'),
            status=UserPlan.Status.RELEASED,
        )
        assert (
            UserPlanRequest.objects.filter(
                user_plan=self.user_plan,
                tp=UserPlanRequest.Type.EARLY_END,
                status=UserPlanRequest.Status.CREATED,
                amount__in=[Decimal('100.0'), Decimal('19.0'), Decimal('1.80'), Decimal('6.20')],
            ).count()
            == 4
        )

    def test_when_plan_is_not_instantly_unstakable_then_error_is_raised(self):
        self.plan.is_instantly_unstakable = False
        self.plan.save(update_fields=['is_instantly_unstakable'])
        with pytest.raises(PlanIsNotInstantlyUnstakable):
            add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('6.98'))

        assert UserPlanRequest.objects.filter(amount=Decimal('6.98'), user_plan=self.user_plan).exists() is False

    def test_when_requested_amount_is_less_than_zero_then_error_is_raised(self):
        with pytest.raises(InvalidAmount) as e:
            add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('-43'))

        assert e.value.message == 'Amount is too low.'
        assert UserPlanRequest.objects.filter(user_plan=self.user_plan).exists() is False

    def test_when_total_stake_amount_becomes_less_than_plan_min_staking_amount_then_error_is_raised(self):
        self.plan.min_staking_amount = 100
        self.plan.save(update_fields=['min_staking_amount'])

        with pytest.raises(InvalidAmount) as e:
            add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('27.1'))

        assert e.value.message == f"Amount is not acceptable. (plan_id: '{self.plan.id}')"
        assert UserPlanRequest.objects.filter(user_plan=self.user_plan).exists() is False

    def test_when_user_has_one_early_end_request_then_second_request_amount_reduces_total_stake_amount_less_than_plan_min_staking(
        self,
    ):
        self.plan.min_staking_amount = 100
        self.plan.save(update_fields=['min_staking_amount'])

        add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('3.5'))
        self.assert_staking_transactions(instant_end_amount=Decimal('3.5'), stake_amount=Decimal('123.5'))
        self.assert_plan_filled_capacity(
            plan_filled_capacity=Decimal('1998.0'),
        )
        self.assert_user_plan_instances(
            locked_amount=Decimal('123.5'),
            early_end_amount=Decimal('3.5'),
            early_end_request_amount=Decimal('3.5'),
        )

        with pytest.raises(InvalidAmount) as e:
            add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('23.6'))
        assert e.value.message == f"Amount is not acceptable. (plan_id: '{self.plan.id}')"
        assert UserPlanRequest.objects.filter(user_plan=self.user_plan, amount=Decimal('23.6')).exists() is False
        self.assert_user_plan_instances(
            locked_amount=Decimal('123.5'),
            early_end_amount=Decimal('3.5'),
            early_end_request_amount=Decimal('3.5'),
        )

    @patch('exchange.staking.errors.report_exception')
    def test_when_user_has_no_user_plan_in_plan_then_no_user_request_is_created_and_report_exception_is_called(
        self, mock_report_exception
    ):
        plan = self.create_plan(**self.get_plan_kwargs())
        user_stake_transaction = self.create_staking_transaction(
            StakingTransaction.TYPES.stake,
            Decimal('126.0'),
            plan=plan,
            user=self.user,
        )
        self.plan.total_capacity = Decimal('100000')
        self.plan.filled_capacity = Decimal('201.5')

        add_and_apply_instant_end_request(self.user.id, plan.id, Decimal('13.70'))

        self.assert_staking_transactions(
            instant_end_amount=Decimal('13.7'),
            stake_amount=Decimal('112.3'),
            plan=plan,
            user_stake_transaction=user_stake_transaction,
        )
        assert UserPlanRequest.objects.filter(amount=Decimal('13.7')).exists() is False
        assert UserPlan.objects.filter(plan=plan, user=self.user).exists() is False
        mock_report_exception.assert_called_once()

    @patch('exchange.staking.errors.report_exception')
    def test_when_user_has_user_plan_with_status_other_than_locked_then_no_user_request_is_created_and_report_exception_is_called(
        self, mock_report_exception
    ):
        self.user_plan.status = UserPlan.Status.REQUESTED
        self.user_plan.save(update_fields=['status'])

        add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('1.7'))

        self.assert_staking_transactions(instant_end_amount=Decimal('1.7'), stake_amount=Decimal('125.3'))
        assert UserPlanRequest.objects.filter(amount=Decimal('1.7')).exists() is False
        assert UserPlan.objects.filter(plan=self.plan, user=self.user, status=UserPlan.Status.REQUESTED).exists()
        mock_report_exception.assert_called_once()

    def test_when_plan_is_ended_then_error_is_raised(self):
        self.plan.staked_at = ir_now() - self.plan.staking_period
        self.plan.save(update_fields=['staked_at'])

        with pytest.raises(CantEndReleasedStaking):
            add_and_apply_instant_end_request(self.user.id, self.plan.id, Decimal('3.1'))

        assert UserPlanRequest.objects.filter(amount=Decimal('3.1')).exists() is False

    def test_when_plan_id_does_not_exist_then_error_is_raised(self):
        plan_id = Plan.objects.latest('id').id + 10
        with pytest.raises(InvalidPlanId):
            add_and_apply_instant_end_request(self.user.id, plan_id, Decimal('3.156'))
        assert UserPlanRequest.objects.filter(amount=Decimal('3.1')).exists() is False
