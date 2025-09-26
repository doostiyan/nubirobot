from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import TestCase

from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from exchange.staking.errors import AlreadyCreated, InvalidPlanId, ParentIsNotCreated, TooSoon
from exchange.staking.helpers import StakingFeatureFlags
from exchange.staking.models import Plan, StakingTransaction, UserPlan
from exchange.staking.service.end_staking import end_all_users_staking, end_user_staking
from tests.staking.utils import StakingTestDataMixin


class EndUserStakingServiceTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = self.create_user()
        self.user_stake_transaction = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake,
            amount=Decimal('103'),
            plan=self.plan,
            user=self.user,
        )

        self.plan.staked_at = ir_now() - self.plan.staking_period - timedelta(days=2)
        self.plan.save(update_fields=['staked_at'])

    def test_when_user_has_no_stake_transaction_then_error_is_raised(self):
        plan = self.create_plan(**self.get_plan_kwargs())
        plan.staked_at = ir_now() - self.plan.staking_period - timedelta(days=2)
        plan.save(update_fields=['staked_at'])

        with pytest.raises(ParentIsNotCreated):
            end_user_staking(self.user.id, plan.id)

        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=plan,
                tp=StakingTransaction.TYPES.extend_out,
            ).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=plan,
                tp=StakingTransaction.TYPES.unstake,
            ).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=plan,
                tp=StakingTransaction.TYPES.system_accepted_end,
            ).exists()
            == False
        )

    def test_when_already_extended_staking_then_error_is_raised(self):
        self.user_stake_transaction = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.extend_out,
            parent=self.user_stake_transaction,
            amount=self.user_stake_transaction.amount,
            plan=self.plan,
            user=self.user,
        )
        with pytest.raises(AlreadyCreated):
            end_user_staking(self.user.id, self.plan.id)

        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                tp=StakingTransaction.TYPES.unstake,
            ).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                tp=StakingTransaction.TYPES.system_accepted_end,
            ).exists()
            == False
        )

    def test_when_user_enabled_auto_extend_and_has_no_end_request_then_all_user_assets_are_extended(self):
        # user enables auto extend ( deactivates auto end)
        auto_end_transaction = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.auto_end_request,
            amount=Decimal('0.0'),
            plan=self.plan,
            user=self.user,
        )
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.deactivator,
            parent=auto_end_transaction,
            amount=Decimal('0.0'),
            plan=self.plan,
            user=self.user,
        )

        end_user_staking(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            parent=self.user_stake_transaction,
            amount=Decimal('103'),
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                tp=StakingTransaction.TYPES.unstake,
            ).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                tp=StakingTransaction.TYPES.system_accepted_end,
            ).exists()
            == False
        )

    def test_when_user_has_active_all_end_request_then_all_user_assets_unstaked_and_nothing_extends(self):
        end_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.end_request,
            amount=Decimal('103'),
            plan=self.plan,
            user=self.user,
        )

        end_user_staking(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            amount=Decimal('0.0'),
            parent=self.user_stake_transaction,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('103'),
            parent=end_request,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.system_accepted_end,
            amount=Decimal('103'),
            parent=end_request,
        )

    def test_when_user_has_active_partial_end_request_then_unstake_end_requested_amount_and_remaining_amount_extends(
        self,
    ):
        end_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.end_request,
            amount=Decimal('90'),
            plan=self.plan,
            user=self.user,
        )

        end_user_staking(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            amount=Decimal('13.0'),
            parent=self.user_stake_transaction,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('90.0'),
            parent=end_request,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.system_accepted_end,
            amount=Decimal('90.0'),
            parent=end_request,
        )

    def test_when_end_request_amount_is_larger_than_staked_amount_then_no_more_than_staked_amount_is_unstaked(self):
        end_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.end_request,
            amount=Decimal('170'),
            plan=self.plan,
            user=self.user,
        )

        end_user_staking(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            amount=Decimal('0.0'),
            parent=self.user_stake_transaction,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('103'),
            parent=end_request,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.system_accepted_end,
            amount=Decimal('103'),
            parent=end_request,
        )

    def test_when_end_request_is_negative_no_more_than_staked_amount_is_extended(self):
        end_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.end_request,
            amount=Decimal('-170'),
            plan=self.plan,
            user=self.user,
        )

        end_user_staking(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            amount=Decimal('103'),
            parent=self.user_stake_transaction,
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                tp=StakingTransaction.TYPES.unstake,
            ).exists()
            == False
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.system_accepted_end,
            amount=Decimal('0.0'),
            parent=end_request,
        )

    def test_when_plan_is_in_staking_period_then_too_soon_error_is_raised(self):
        plan = self.create_plan(**self.get_plan_kwargs())
        with pytest.raises(TooSoon):
            end_user_staking(self.user.id, plan.id)

        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=plan,
                tp=StakingTransaction.TYPES.extend_out,
            ).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=plan,
                tp=StakingTransaction.TYPES.unstake,
            ).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=plan,
                tp=StakingTransaction.TYPES.system_accepted_end,
            ).exists()
            == False
        )

    def test_when_user_has_disabled_auto_extend_and_has_end_request_too_then_auto_extend_is_prioritized(self):
        # disable auto extend ( enable auto end)
        auto_end_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.auto_end_request,
            amount=Decimal('0.0'),
            plan=self.plan,
            user=self.user,
        )
        # end request
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.end_request,
            amount=Decimal('13'),
            plan=self.plan,
            user=self.user,
        )

        end_user_staking(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            amount=Decimal('0.0'),
            parent=self.user_stake_transaction,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('103'),
            parent=auto_end_request,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.system_accepted_end,
            amount=Decimal('103'),
            parent=auto_end_request,
        )

    def test_when_user_has_active_partial_instant_end_request_then_unstake_instant_end_amount_and_remaining_amount_extends(
        self,
    ):
        instant_end_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.instant_end_request,
            amount=Decimal('70'),
            plan=self.plan,
            user=self.user,
        )

        end_user_staking(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            amount=Decimal('33.0'),
            parent=self.user_stake_transaction,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('70.0'),
            parent=instant_end_request,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.system_accepted_end,
            amount=Decimal('70.0'),
            parent=instant_end_request,
        )

    def test_when_user_has_disabled_auto_extend_then_all_assets_are_unstaked_and_nothing_extends(self):
        # disable auto extend ( enable auto end)
        auto_end_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.auto_end_request,
            amount=Decimal('0.0'),
            plan=self.plan,
            user=self.user,
        )

        end_user_staking(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            amount=Decimal('0.0'),
            parent=self.user_stake_transaction,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('103'),
            parent=auto_end_request,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.system_accepted_end,
            amount=Decimal('103'),
            parent=auto_end_request,
        )

    def test_auto_end_request_transaction_amount_is_not_important_and_it_unstakes_all_user_assets(self):
        # disable auto extend ( enable auto end)
        auto_end_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.auto_end_request,
            amount=Decimal('300'),
            plan=self.plan,
            user=self.user,
        )

        end_user_staking(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            amount=Decimal('0.0'),
            parent=self.user_stake_transaction,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('103'),
            parent=auto_end_request,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.system_accepted_end,
            amount=Decimal('103'),
            parent=auto_end_request,
        )

    def test_when_plan_is_not_extendable_then_all_user_assets_unstaked_and_nothing_extends(self):
        self.plan.is_extendable = False
        self.plan.save(update_fields=['is_extendable'])

        end_user_staking(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            amount=Decimal('0.0'),
            parent=self.user_stake_transaction,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('103'),
            parent=None,
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                tp=StakingTransaction.TYPES.system_accepted_end,
            ).exists()
            == False
        )

    def test_when_user_has_active_all_instant_end_request_then_all_user_assets_unstaked_and_nothing_extends(self):
        instant_end_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.instant_end_request,
            amount=Decimal('103'),
            plan=self.plan,
            user=self.user,
        )

        end_user_staking(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            amount=Decimal('0.0'),
            parent=self.user_stake_transaction,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('103'),
            parent=instant_end_request,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.system_accepted_end,
            amount=Decimal('103'),
            parent=instant_end_request,
        )

    def test_when_instant_end_request_is_negative_no_more_than_staked_amount_is_extended(self):
        instant_end_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.instant_end_request,
            amount=Decimal('-170'),
            plan=self.plan,
            user=self.user,
        )

        end_user_staking(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            amount=Decimal('103'),
            parent=self.user_stake_transaction,
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                tp=StakingTransaction.TYPES.unstake,
            ).exists()
            == False
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.system_accepted_end,
            amount=Decimal('0.0'),
            parent=instant_end_request,
        )

    def test_when_active_instant_end_request_amount_is_larger_than_staked_amount_then_no_more_than_staked_amount_is_unstaked(
        self,
    ):
        instant_end_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.instant_end_request,
            amount=Decimal('4000'),
            plan=self.plan,
            user=self.user,
        )

        end_user_staking(self.user.id, self.plan.id)

        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            amount=Decimal('0.0'),
            parent=self.user_stake_transaction,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('103'),
            parent=instant_end_request,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.system_accepted_end,
            amount=Decimal('103'),
            parent=instant_end_request,
        )

    def test_when_plan_id_is_not_valid_then_invalid_plan_id_error_is_raised(self):
        plan_id = Plan.objects.latest('id').id + 100

        with pytest.raises(InvalidPlanId):
            end_user_staking(self.user.id, plan_id)

        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan_id=plan_id,
                tp=StakingTransaction.TYPES.extend_out,
            ).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan_id=plan_id,
                tp=StakingTransaction.TYPES.unstake,
            ).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan_id=plan_id,
                tp=StakingTransaction.TYPES.system_accepted_end,
            ).exists()
            == False
        )


class EndUserStakingNewModelsTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = self.create_user()
        self.user_stake_transaction = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake,
            amount=Decimal('30.0'),
            plan=self.plan,
            user=self.user,
        )

        self.plan.staked_at = ir_now() - self.plan.staking_period - timedelta(days=2)
        self.plan.save(update_fields=['staked_at'])

        self.user_plan = UserPlan.objects.create(
            user=self.user,
            plan=self.plan,
            locked_amount=Decimal('30.0'),
            status=UserPlan.Status.LOCKED,
            auto_renewal=True,
        )

        Settings.set(StakingFeatureFlags.CRONJOB_DUAL_WRITE, 'yes')

    def test_when_user_enabled_auto_renewal_then_all_user_assets_extend_successfully(self):
        end_all_users_staking(self.plan.id)

        assert UserPlan.objects.get(
            user=self.user,
            plan=self.plan,
            locked_amount=Decimal('30.0'),
            status=UserPlan.Status.EXTEND_TO_NEXT_CYCLE,
            extended_to_next_cycle_amount=Decimal('30.0'),
            unlocked_at__isnull=True,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            parent=self.user_stake_transaction,
            amount=Decimal('30.0'),
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                tp=StakingTransaction.TYPES.unstake,
            ).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                tp=StakingTransaction.TYPES.system_accepted_end,
            ).exists()
            == False
        )

    def test_when_user_disabled_auto_renewal_then_nothing_extends_and_user_plan_waits_for_release(self):
        self.user_plan.auto_renewal = False
        self.user_plan.save(update_fields=['auto_renewal'])
        auto_end_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.auto_end_request,
            amount=Decimal('0.0'),
            plan=self.plan,
            user=self.user,
        )

        end_all_users_staking(self.plan.id)

        assert UserPlan.objects.get(
            user=self.user,
            plan=self.plan,
            locked_amount=Decimal('30.0'),
            status=UserPlan.Status.PENDING_RELEASE,
            extended_to_next_cycle_amount=Decimal('0.0'),
            unlocked_at__isnull=False,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            amount=Decimal('0.0'),
            parent=self.user_stake_transaction,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('30.0'),
            parent=auto_end_request,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.system_accepted_end,
            amount=Decimal('30.0'),
            parent=auto_end_request,
        )

    def test_when_plan_is_not_extendable_then_user_plan_waits_release_and_nothing_extends(self):
        self.plan.is_extendable = False
        self.plan.save(update_fields=['is_extendable'])

        end_all_users_staking(self.plan.id)

        assert UserPlan.objects.get(
            user=self.user,
            plan=self.plan,
            locked_amount=Decimal('30.0'),
            status=UserPlan.Status.PENDING_RELEASE,
            extended_to_next_cycle_amount=Decimal('0.0'),
            unlocked_at__isnull=False,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            amount=Decimal('0.0'),
            parent=self.user_stake_transaction,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('30.0'),
            parent=None,
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                tp=StakingTransaction.TYPES.system_accepted_end,
                amount=Decimal('30.0'),
            ).exists()
            == False
        )

    def test_when_have_users_with_both_enabling_and_disabling_auto_renewal_then_both_renew_and_end_happens_successfully(
        self,
    ):
        user_plan2 = UserPlan.objects.create(
            user=self.create_user(),
            plan=self.plan,
            locked_amount=Decimal('40.1'),
            status=UserPlan.Status.LOCKED,
            auto_renewal=False,
        )

        end_all_users_staking(self.plan.id)

        assert UserPlan.objects.get(
            user=self.user,
            plan=self.plan,
            locked_amount=Decimal('30.0'),
            status=UserPlan.Status.EXTEND_TO_NEXT_CYCLE,
            extended_to_next_cycle_amount=Decimal('30.0'),
            unlocked_at__isnull=True,
        )

        user_plan2.refresh_from_db(fields=['status', 'locked_amount', 'extended_to_next_cycle_amount', 'unlocked_at'])
        assert user_plan2.status == UserPlan.Status.PENDING_RELEASE
        assert user_plan2.locked_amount == Decimal('40.1')
        assert user_plan2.extended_to_next_cycle_amount == Decimal('0.0')
        assert user_plan2.unlocked_at is not None

    def test_when_user_has_no_user_plan_then_no_update_happens(self):
        self.user_plan.delete()

        end_all_users_staking(self.plan.id)

        assert UserPlan.objects.filter(user=self.user, plan=self.plan).exists() == False

    def test_when_dual_write_feature_flag_is_not_enabled_then_no_new_model_instance_updates(self):
        Settings.set(StakingFeatureFlags.CRONJOB_DUAL_WRITE, 'no')

        end_all_users_staking(self.plan.id)

        assert UserPlan.objects.get(
            user=self.user,
            plan=self.plan,
            locked_amount=Decimal('30.0'),
            status=UserPlan.Status.LOCKED,
            extended_to_next_cycle_amount=Decimal('0.0'),
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            parent=self.user_stake_transaction,
            amount=Decimal('30.0'),
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                tp=StakingTransaction.TYPES.unstake,
            ).exists()
            == False
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                tp=StakingTransaction.TYPES.system_accepted_end,
            ).exists()
            == False
        )

    @patch('exchange.staking.service.end_staking.Settings.get_flag')
    @patch('exchange.staking.errors.report_exception')
    def test_when_end_user_plan_has_unknown_error_then_no_new_model_instance_is_updates_and_report_exception_is_called(
        self, mocked_report_exception, mocked_internal_function
    ):
        mocked_internal_function.side_effect = Exception
        self.plan.is_extendable = False
        self.plan.save(update_fields=['is_extendable'])

        end_all_users_staking(self.plan.id)

        mocked_report_exception.assert_called_once()
        assert UserPlan.objects.get(
            user=self.user,
            plan=self.plan,
            locked_amount=Decimal('30.0'),
            status=UserPlan.Status.LOCKED,
            extended_to_next_cycle_amount=Decimal('0.0'),
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_out,
            amount=Decimal('0.0'),
            parent=self.user_stake_transaction,
        )
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('30.0'),
            parent=None,
        )
        assert (
            StakingTransaction.objects.filter(
                user=self.user,
                plan=self.plan,
                tp=StakingTransaction.TYPES.system_accepted_end,
                amount=Decimal('30.0'),
            ).exists()
            == False
        )

    @patch('exchange.staking.service.end_staking.end_user_staking')
    def test_when_user_plan_is_not_in_lock_status_no_update_happens(self, mocked_end_staking):
        mocked_end_staking.return_value = None

        self.user_plan.status = UserPlan.Status.EXTEND_TO_NEXT_CYCLE
        self.user_plan.save(update_fields=['status'])
        end_all_users_staking(self.plan.id)
        assert UserPlan.objects.get(
            user=self.user,
            plan=self.plan,
            locked_amount=Decimal('30.0'),
            status=UserPlan.Status.EXTEND_TO_NEXT_CYCLE,
            auto_renewal=True,
            extended_to_next_cycle_amount=Decimal('0.0'),
        )

        self.user_plan.status = UserPlan.Status.USER_CANCELED
        self.user_plan.save(update_fields=['status'])
        end_all_users_staking(self.plan.id)
        assert UserPlan.objects.get(
            user=self.user,
            plan=self.plan,
            locked_amount=Decimal('30.0'),
            status=UserPlan.Status.USER_CANCELED,
            auto_renewal=True,
            extended_to_next_cycle_amount=Decimal('0.0'),
        )

        self.user_plan.status = UserPlan.Status.REQUESTED
        self.user_plan.save(update_fields=['status'])
        end_all_users_staking(self.plan.id)
        assert UserPlan.objects.get(
            user=self.user,
            plan=self.plan,
            locked_amount=Decimal('30.0'),
            status=UserPlan.Status.REQUESTED,
            auto_renewal=True,
            extended_to_next_cycle_amount=Decimal('0.0'),
        )

        self.user_plan.status = UserPlan.Status.ADMIN_REJECTED
        self.user_plan.save(update_fields=['status'])
        end_all_users_staking(self.plan.id)
        assert UserPlan.objects.get(
            user=self.user,
            plan=self.plan,
            locked_amount=Decimal('30.0'),
            status=UserPlan.Status.ADMIN_REJECTED,
            auto_renewal=True,
            extended_to_next_cycle_amount=Decimal('0.0'),
        )

        self.user_plan.status = UserPlan.Status.EXTEND_FROM_PREVIOUS_CYCLE
        self.user_plan.save(update_fields=['status'])
        end_all_users_staking(self.plan.id)
        assert UserPlan.objects.get(
            user=self.user,
            plan=self.plan,
            locked_amount=Decimal('30.0'),
            status=UserPlan.Status.EXTEND_FROM_PREVIOUS_CYCLE,
            auto_renewal=True,
            extended_to_next_cycle_amount=Decimal('0.0'),
        )

        self.user_plan.status = UserPlan.Status.RELEASED
        self.user_plan.save(update_fields=['status'])
        end_all_users_staking(self.plan.id)
        assert UserPlan.objects.get(
            user=self.user,
            plan=self.plan,
            locked_amount=Decimal('30.0'),
            status=UserPlan.Status.RELEASED,
            auto_renewal=True,
            extended_to_next_cycle_amount=Decimal('0.0'),
        )

        self.user_plan.status = UserPlan.Status.PENDING_RELEASE
        self.user_plan.save(update_fields=['status'])
        end_all_users_staking(self.plan.id)
        assert UserPlan.objects.get(
            user=self.user,
            plan=self.plan,
            locked_amount=Decimal('30.0'),
            status=UserPlan.Status.PENDING_RELEASE,
            auto_renewal=True,
            extended_to_next_cycle_amount=Decimal('0.0'),
        )

    def test_when_plan_is_in_staking_period_then_too_soon_error_is_raised(self):
        plan = self.create_plan(**self.get_plan_kwargs())
        with pytest.raises(TooSoon):
            end_user_staking(self.user.id, plan.id)

    @patch('exchange.staking.errors.report_exception')
    def test_when_plan_id_is_invalid_then_error_is_raised(self, mocked_report_exception):
        plan_id = Plan.objects.latest('id').id + 100

        end_all_users_staking(plan_id)

        assert UserPlan.objects.get(
            user=self.user,
            plan=self.plan,
            locked_amount=Decimal('30.0'),
            status=UserPlan.Status.LOCKED,
            auto_renewal=True,
            extended_to_next_cycle_amount=Decimal('0.0'),
        )
        assert UserPlan.objects.filter(plan_id=plan_id).exists() == False
        assert mocked_report_exception.call_count == 1
