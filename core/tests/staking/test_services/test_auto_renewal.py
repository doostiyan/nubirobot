from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import TestCase

from exchange.base.models import Settings
from exchange.staking.errors import InvalidPlanId, NonExtendablePlan, TooLate
from exchange.staking.helpers import StakingFeatureFlags
from exchange.staking.models import Plan, StakingTransaction, UserPlan
from exchange.staking.service.auto_renewal import set_plan_auto_renewal, validate_can_auto_renew_plan
from tests.staking.utils import StakingTestDataMixin


class SetAutoRenewalServiceTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = self.create_user()

    def test_disable_plan_auto_renewal(self):
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=False)

        assert StakingTransaction.objects.get(
            plan=self.plan, user=self.user, tp=StakingTransaction.TYPES.auto_end_request, child=None
        )

    def test_disable_plan_auto_renewal_multiple_times(self):
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=False)
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=False)

        assert StakingTransaction.objects.get(
            plan=self.plan, user=self.user, tp=StakingTransaction.TYPES.auto_end_request, child=None
        )

    def test_enable_plan_auto_renewal_when_user_has_not_disabled_it_yet(self):
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True)

        assert (
            StakingTransaction.objects.filter(
                plan=self.plan,
                user=self.user,
                tp=StakingTransaction.TYPES.auto_end_request,
            ).exists()
            is False
        )
        assert (
            StakingTransaction.objects.filter(
                plan=self.plan,
                user=self.user,
                tp=StakingTransaction.TYPES.deactivator,
            ).exists()
            is False
        )

    def test_enable_auto_renewal_when_user_has_disabled_plan_before(self):
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=False)

        assert StakingTransaction.objects.filter(
            plan=self.plan, user=self.user, tp=StakingTransaction.TYPES.auto_end_request, child=None
        ).exists()

        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True)

        auto_end_request = StakingTransaction.objects.get(
            plan=self.plan,
            user=self.user,
            tp=StakingTransaction.TYPES.auto_end_request,
        )
        assert StakingTransaction.objects.filter(
            plan=self.plan, user=self.user, tp=StakingTransaction.TYPES.deactivator, parent=auto_end_request
        ).exists()

    def test_enable_plan_auto_renewal_when_plan_is_not_extendable_then_nothing_happens(self):
        self.plan.is_extendable = False
        self.plan.save(update_fields=['is_extendable'])

        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True)

        assert (
            StakingTransaction.objects.filter(
                plan=self.plan,
                user=self.user,
                tp=StakingTransaction.TYPES.auto_end_request,
            ).exists()
            is False
        )
        assert (
            StakingTransaction.objects.filter(
                plan=self.plan,
                user=self.user,
                tp=StakingTransaction.TYPES.deactivator,
            ).exists()
            is False
        )

    def test_disable_plan_auto_renewal_when_plan_is_not_extendable_then_nothing_happens(self):
        self.plan.is_extendable = False
        self.plan.save(update_fields=['is_extendable'])

        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True)

        assert (
            StakingTransaction.objects.filter(
                plan=self.plan,
                user=self.user,
                tp=StakingTransaction.TYPES.auto_end_request,
            ).exists()
            is False
        )
        assert (
            StakingTransaction.objects.filter(
                plan=self.plan,
                user=self.user,
                tp=StakingTransaction.TYPES.deactivator,
            ).exists()
            is False
        )

    def test_when_set_plan_auto_renewal_is_called_with_none_value_then_no_changes_happen(self):
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=False)
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True)
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=None)

        auto_end_request = StakingTransaction.objects.get(
            plan=self.plan,
            user=self.user,
            tp=StakingTransaction.TYPES.auto_end_request,
        )
        assert StakingTransaction.objects.filter(
            plan=self.plan, user=self.user, tp=StakingTransaction.TYPES.deactivator, parent=auto_end_request
        ).exists()

    def test_when_plan_does_not_exist_then_error_is_raised(self):
        plan_id = Plan.objects.latest('id').id + 10

        with pytest.raises(InvalidPlanId):
            set_plan_auto_renewal(plan_id=plan_id, user_id=self.user.id, allow_renewal=True)
            set_plan_auto_renewal(plan_id=plan_id, user_id=self.user.id, allow_renewal=False)
            set_plan_auto_renewal(plan_id=plan_id, user_id=self.user.id, allow_renewal=True)

        assert (
            StakingTransaction.objects.filter(
                plan_id=plan_id,
                user=self.user,
                tp=StakingTransaction.TYPES.auto_end_request,
            ).exists()
            is False
        )
        assert (
            StakingTransaction.objects.filter(
                plan_id=plan_id,
                user=self.user,
                tp=StakingTransaction.TYPES.deactivator,
            ).exists()
        ) is False


class SetAutoRenewalNewModelsTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = self.create_user()
        self.user_plan = UserPlan.objects.create(
            user=self.user,
            plan=self.plan,
            status=UserPlan.Status.LOCKED,
            locked_amount=Decimal('10'),
            auto_renewal=False,
        )

        Settings.set(StakingFeatureFlags.API_DUAL_WRITE, 'yes')

    def test_when_staking_dual_write_feature_flag_is_disabled_then_user_plan_not_changes(self):
        Settings.set(StakingFeatureFlags.API_DUAL_WRITE, 'no')

        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True)

        assert (
            StakingTransaction.objects.filter(
                plan=self.plan,
                user=self.user,
                tp=StakingTransaction.TYPES.auto_end_request,
            ).exists()
            is False
        )
        assert (
            StakingTransaction.objects.filter(
                plan=self.plan,
                user=self.user,
                tp=StakingTransaction.TYPES.deactivator,
            ).exists()
            is False
        )
        self.user_plan.refresh_from_db(fields=['auto_renewal'])
        assert self.user_plan.auto_renewal is False

    def test_enable_plan_auto_renewal_creates_both_new_and_old_model_instances(self):
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True)

        assert (
            StakingTransaction.objects.filter(
                plan=self.plan,
                user=self.user,
                tp=StakingTransaction.TYPES.auto_end_request,
            ).exists()
            is False
        )
        assert (
            StakingTransaction.objects.filter(
                plan=self.plan,
                user=self.user,
                tp=StakingTransaction.TYPES.deactivator,
            ).exists()
            is False
        )
        self.user_plan.refresh_from_db(fields=['auto_renewal'])
        assert self.user_plan.auto_renewal is True

    def test_disable_plan_auto_renewal_creates_both_new_and_pld_model_instances(self):
        self.user_plan.auto_renewal = True
        self.user_plan.save(update_fields=['auto_renewal'])

        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=False)

        assert StakingTransaction.objects.get(
            plan=self.plan, user=self.user, tp=StakingTransaction.TYPES.auto_end_request, child=None
        )
        self.user_plan.refresh_from_db(fields=['auto_renewal'])
        assert self.user_plan.auto_renewal is False

    def test_when_user_has_no_user_plan_then_no_new_model_instance_changes(self):
        plan = self.create_plan(**self.get_plan_kwargs())
        set_plan_auto_renewal(plan_id=plan.id, user_id=self.user.id, allow_renewal=True)

        assert UserPlan.objects.filter(user=self.user, plan=plan, auto_renewal=True).exists() is False

    def test_when_user_plan_is_not_in_right_status_then_nothing_happens(self):
        self.user_plan.status = UserPlan.Status.RELEASED
        self.user_plan.save(update_fields=['status'])
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True)

        self.user_plan.status = UserPlan.Status.EXTEND_TO_NEXT_CYCLE
        self.user_plan.save(update_fields=['status'])
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True)

        self.user_plan.status = UserPlan.Status.ADMIN_REJECTED
        self.user_plan.save(update_fields=['status'])
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True)

        self.user_plan.status = UserPlan.Status.PENDING_RELEASE
        self.user_plan.save(update_fields=['status'])
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True)

        self.user_plan.refresh_from_db(fields=['auto_renewal'])
        assert self.user_plan.auto_renewal is False

    def test_when_plan_is_not_extendable_then_nothing_happens(self):
        self.plan.is_extendable = False
        self.plan.save(update_fields=['is_extendable'])

        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True)

        self.user_plan.refresh_from_db(fields=['auto_renewal'])
        assert self.user_plan.auto_renewal is False

    def test_when_set_plan_auto_renewal_is_called_with_none_value_then_nothing_happens(self):
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=False)
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True)
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=None)

        self.user_plan.refresh_from_db(fields=['auto_renewal'])
        assert self.user_plan.auto_renewal is True


    @patch('exchange.staking.service.auto_renewal.Settings.get_flag')
    @patch('exchange.staking.errors.report_exception')
    def test_when_set_user_plan_auto_renewal_raises_unknown_error_then_old_instances_are_created_and_report_exception_is_called(
        self, mock_report_exception, mock_inner_set_user_plan_auto_renewal
    ):
        mock_inner_set_user_plan_auto_renewal.side_effect = Exception

        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True)
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=False)
        set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True)

        mock_report_exception.assert_called()
        assert mock_inner_set_user_plan_auto_renewal.call_count == 3
        self.user_plan.refresh_from_db(fields=['auto_renewal'])
        assert self.user_plan.auto_renewal is False
        auto_end_request = StakingTransaction.objects.get(
            plan=self.plan,
            user=self.user,
            tp=StakingTransaction.TYPES.auto_end_request,
        )
        assert StakingTransaction.objects.filter(
            plan=self.plan, user=self.user, tp=StakingTransaction.TYPES.deactivator, parent=auto_end_request
        ).exists()

    def test_when_plan_staking_period_is_finished_then_error_is_raised(self):
        self.plan.staked_at -= timedelta(days=3)
        self.plan.save(update_fields=('staked_at',))

        with pytest.raises(TooLate):
            set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True)
            set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=False)
            set_plan_auto_renewal(plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True)

        self.user_plan.refresh_from_db(fields=['auto_renewal'])
        assert self.user_plan.auto_renewal is False
        assert (
            StakingTransaction.objects.filter(
                plan=self.plan,
                user=self.user,
                tp=StakingTransaction.TYPES.auto_end_request,
            ).exists()
            is False
        )
        assert (
            StakingTransaction.objects.filter(
                plan=self.plan,
                user=self.user,
                tp=StakingTransaction.TYPES.deactivator,
            ).exists()
            is False
        )

    def test_when_plan_does_not_exist_then_error_is_raised(self):
        plan_id = Plan.objects.latest('id').id + 10

        with pytest.raises(InvalidPlanId):
            set_plan_auto_renewal(plan_id=plan_id, user_id=self.user.id, allow_renewal=True)
            set_plan_auto_renewal(plan_id=plan_id, user_id=self.user.id, allow_renewal=False)
            set_plan_auto_renewal(plan_id=plan_id, user_id=self.user.id, allow_renewal=True)

        assert UserPlan.objects.filter(user=self.user, plan_id=plan_id).exists() is False


class ValidateCanAutoRenewPlanTest(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())

    def test_when_plan_is_not_extendable_then_error_is_raised(self):
        self.plan.is_extendable = False
        self.plan.save(update_fields=['is_extendable'])

        with pytest.raises(NonExtendablePlan):
            validate_can_auto_renew_plan(self.plan.id)

    def test_when_plan_is_extendable_then_no_error_is_raised(self):
        validate_can_auto_renew_plan(self.plan.id)

    def test_when_plan_does_not_exist_then_error_is_raised(self):
        with pytest.raises(InvalidPlanId):
            validate_can_auto_renew_plan(Plan.objects.latest('id').id + 10)
