from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from exchange.config.config.models import Currencies
from exchange.staking.errors import (
    InsufficientWalletBalance,
    InvalidAmount,
    LowPlanCapacity,
    RecentlyCanceled,
    TooLate,
    TooSoon,
)
from exchange.staking.helpers import StakingFeatureFlags
from exchange.staking.models import (
    ExternalEarningPlatform,
    Plan,
    StakingTransaction,
    UserPlan,
    UserPlanRequest,
    UserPlanWalletTransaction,
)
from exchange.staking.service.reject_requests.subscription import reject_user_subscription
from exchange.staking.service.subscription import subscribe
from exchange.wallet.models import Transaction
from tests.staking.utils import StakingTestDataMixin


class PlanSubscriptionTest(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = User.objects.get(id=202)
        self.wallet = self.charge_wallet(self.user, self.plan.currency, Decimal('1000'))
        self.plan.total_capacity = Decimal('100000')
        self.plan.filled_capacity = Decimal('0')
        self.plan.save(
            update_fields=('total_capacity', 'filled_capacity'),
        )

    def assert_staking_transactions(
        self,
        staking_transaction_amount: Decimal,
        wallet_transaction_amount: Decimal,
        filled_capacity: Decimal,
        wallet_transaction_ref_module=132,
        wallet_transaction_tp=130,
        plan: Plan = None,
    ):
        plan = plan or self.plan
        plan.refresh_from_db(fields=['filled_capacity'])
        assert plan.filled_capacity == filled_capacity
        staking_transaction = StakingTransaction.objects.get(
            user=self.user, plan=plan, amount=staking_transaction_amount
        )
        wallet_transaction = Transaction.objects.get(
            wallet=self.wallet,
            ref_module=wallet_transaction_ref_module,
            ref_id=staking_transaction.id,
            tp=wallet_transaction_tp,
            description=f'درخواست مشارکت در {plan.fa_description}',
            amount=wallet_transaction_amount,
        )
        assert staking_transaction.wallet_transaction == wallet_transaction

    def test_subscribe_user_to_staking_plan_successfully(self):
        subscribe(self.user, self.plan.id, Decimal('155.5'))

        self.assert_staking_transactions(
            Decimal('155.5'),
            -Decimal('155.5'),
            Decimal('155.5'),
        )

    def test_subscribe_user_to_yield_farming_plan_successfully(self):
        yield_plan = self.create_plan(
            **self.get_plan_kwargs(
                external_platform=self.add_external_platform(
                    Currencies.btc, ExternalEarningPlatform.TYPES.yield_aggregator
                )
            )
        )
        yield_plan.total_capacity = Decimal('100000')
        yield_plan.filled_capacity = Decimal('0')
        yield_plan.save()
        subscribe(self.user, yield_plan.id, Decimal('133.5'))

        self.assert_staking_transactions(
            Decimal('133.5'),
            -Decimal('133.5'),
            Decimal('133.5'),
            wallet_transaction_ref_module=162,
            wallet_transaction_tp=160,
            plan=yield_plan,
        )

    def test_subscribe_user_to_plan_when_user_has_multiple_subscribe_requests(self):
        subscribe(self.user, self.plan.id, Decimal('115'))
        self.assert_staking_transactions(
            Decimal('115'),
            -Decimal('115'),
            Decimal('115'),
        )

        subscribe(self.user, self.plan.id, Decimal('10.7'))
        self.assert_staking_transactions(
            Decimal('115') + Decimal('10.7'),
            -Decimal('10.7'),
            Decimal('115') + Decimal('10.7'),
        )

    def test_subscribe_fails_when_user_does_not_have_enough_balance_in_wallet(self):
        with pytest.raises(InsufficientWalletBalance):
            subscribe(self.user, self.plan.id, Decimal('30000'))

        assert (
            StakingTransaction.objects.filter(amount=Decimal('431.77'), user=self.user, plan=self.plan).exists()
            is False
        )

    def test_subscribe_fails_when_amount_is_less_than_zero(self):
        with pytest.raises(InvalidAmount):
            subscribe(self.user, self.plan.id, Decimal('-11'))

        assert StakingTransaction.objects.filter(user=self.user, plan=self.plan).exists() is False

    def test_subscribe_fails_when_amount_is_less_than_plan_min_staking_amount(self):
        with pytest.raises(InvalidAmount):
            subscribe(self.user, self.plan.id, Decimal('4.9'))

        assert (
            StakingTransaction.objects.filter(amount=Decimal('4.9'), user=self.user, plan=self.plan).exists() is False
        )

    def test_subscribe_fails_when_plan_has_lower_capacity(self):
        self.plan.filled_capacity += self.plan.total_capacity - Decimal('89.9')
        self.plan.save(update_fields=['filled_capacity'])
        with pytest.raises(LowPlanCapacity):
            subscribe(self.user, self.plan.id, Decimal('90'))

        assert StakingTransaction.objects.filter(amount=Decimal('90'), user=self.user, plan=self.plan).exists() is False

    def test_subscribe_fails_when_plan_is_not_yet_open_to_accept_request(self):
        self.plan.opened_at = ir_now() + timedelta(days=2)
        self.plan.save(
            update_fields=('opened_at',),
        )

        with pytest.raises(TooSoon):
            subscribe(self.user, self.plan.id, Decimal('190'))

        assert (
            StakingTransaction.objects.filter(amount=Decimal('190'), user=self.user, plan=self.plan).exists() is False
        )

    def test_subscribe_fails_when_it_is_after_plan_request_period(self):
        self.plan.opened_at -= timedelta(days=4)
        self.plan.save(
            update_fields=('opened_at',),
        )

        with pytest.raises(TooLate):
            subscribe(self.user, self.plan.id, Decimal('13'))

        assert StakingTransaction.objects.filter(amount=Decimal('13'), user=self.user, plan=self.plan).exists() is False

    def test_subscribe_fails_when_user_has_recent_reject_create_request(self):
        subscribe(self.user, self.plan.id, Decimal('170'))
        reject_user_subscription(self.user.id, self.plan.id, Decimal('100'))
        with pytest.raises(RecentlyCanceled):
            subscribe(self.user, self.plan.id, Decimal('9.5'))

        assert (
            StakingTransaction.objects.filter(amount=Decimal('9.5'), user=self.user, plan=self.plan).exists() is False
        )


class PlanSubscriptionNewModelsTests(PlanSubscriptionTest):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = self.create_user()
        self.wallet = self.charge_wallet(self.user, self.plan.currency, Decimal('1000'))
        self.plan.total_capacity = Decimal('100000')
        self.plan.filled_capacity = Decimal('0')
        self.plan.save(
            update_fields=('total_capacity', 'filled_capacity'),
        )
        Settings.set(StakingFeatureFlags.API_DUAL_WRITE, value='yes')

    def assert_user_plan_instances(
        self,
        plan_locked_amount: Decimal,
        plan_requested_amount: Decimal,
        user_request_amount: Decimal,
        wallet_transaction_amount: Decimal,
        auto_renewal: bool = False,
        user_plan_status=UserPlan.Status.REQUESTED,
    ):
        user_plan = UserPlan.objects.get(
            user=self.user,
            plan=self.plan,
            requested_amount=plan_requested_amount,
            locked_amount=plan_locked_amount,
            status=user_plan_status,
            auto_renewal=auto_renewal,
        )
        user_request = UserPlanRequest.objects.get(
            user_plan=user_plan,
            amount=user_request_amount,
            tp=UserPlanRequest.Type.SUBSCRIPTION,
            status=UserPlanRequest.Status.CREATED,
        )
        assert UserPlanWalletTransaction.objects.get(
            user_plan=user_plan,
            amount=wallet_transaction_amount,
            tp=UserPlanWalletTransaction.Type.SUBSCRIPTION,
            user_plan_request=user_request,
        )

    def test_when_dual_write_flag_is_disabled_then_no_user_plan_models_instance_are_created(self):
        Settings.set(StakingFeatureFlags.API_DUAL_WRITE, value='no')
        subscribe(self.user, self.plan.id, Decimal('151.5'))

        self.assert_staking_transactions(
            Decimal('151.5'),
            -Decimal('151.5'),
            Decimal('151.5'),
        )
        assert UserPlan.objects.filter(user=self.user, plan=self.plan).exists() is False

    def test_subscribe_user_to_plan_adds_both_user_plan_and_staking_transaction_records(self):
        subscribe(self.user, self.plan.id, Decimal('151.5'), allow_renewal=True)

        self.assert_staking_transactions(
            Decimal('151.5'),
            -Decimal('151.5'),
            Decimal('151.5'),
        )
        self.assert_user_plan_instances(
            plan_locked_amount=Decimal('151.5'),
            plan_requested_amount=Decimal('151.5'),
            user_request_amount=Decimal('151.5'),
            wallet_transaction_amount=-Decimal('151.5'),
            auto_renewal=True,
        )

    def test_subscribe_user_to_plan_when_user_sends_multiple_subscription_request(self):
        subscribe(self.user, self.plan.id, Decimal('10.1'))

        self.assert_staking_transactions(
            Decimal('10.1'),
            -Decimal('10.1'),
            Decimal('10.1'),
        )
        self.assert_user_plan_instances(
            plan_locked_amount=Decimal('10.1'),
            plan_requested_amount=Decimal('10.1'),
            user_request_amount=Decimal('10.1'),
            wallet_transaction_amount=-Decimal('10.1'),
            auto_renewal=False,
        )

        subscribe(self.user, self.plan.id, Decimal('15.0'), allow_renewal=True)
        self.assert_staking_transactions(
            Decimal('25.1'),
            -Decimal('15.0'),
            Decimal('25.1'),
        )
        self.assert_user_plan_instances(
            plan_locked_amount=Decimal('25.1'),
            plan_requested_amount=Decimal('25.1'),
            user_request_amount=Decimal('15.0'),
            wallet_transaction_amount=-Decimal('15.0'),
            auto_renewal=True,
        )

    def test_when_user_plan_is_extended_then_new_requests_are_added_to_existing_user_plan(self):
        UserPlan.objects.create(
            user=self.user,
            plan=self.plan,
            status=UserPlan.Status.EXTEND_FROM_PREVIOUS_CYCLE,
            locked_amount=Decimal('33.6'),
            requested_amount=Decimal('0'),
            extended_from_previous_cycle_amount=Decimal('33.6'),
        )

        subscribe(self.user, self.plan.id, Decimal('10.6'), allow_renewal=True)
        self.assert_staking_transactions(
            Decimal('10.6'),
            -Decimal('10.6'),
            Decimal('10.6'),
        )
        self.assert_user_plan_instances(
            plan_locked_amount=Decimal('44.2'),
            plan_requested_amount=Decimal('10.6'),
            user_request_amount=Decimal('10.6'),
            wallet_transaction_amount=-Decimal('10.6'),
            auto_renewal=True,
            user_plan_status=UserPlan.Status.EXTEND_FROM_PREVIOUS_CYCLE,
        )

    @patch('exchange.staking.service.subscription.check_user_plan_request')
    @patch('exchange.staking.errors.report_exception')
    def test_when_an_unknown_exception_happens_then_old_schema_instances_are_created_and_report_exception_is_called(
        self, mock_report_exception, mocked_inner_add_user_plan_function
    ):
        mocked_inner_add_user_plan_function.side_effect = Exception

        subscribe(self.user, self.plan.id, Decimal('19.5'))

        self.assert_staking_transactions(
            Decimal('19.5'),
            -Decimal('19.5'),
            Decimal('19.5'),
        )
        assert UserPlan.objects.filter(user=self.user, plan=self.plan).exists() is False
        mock_report_exception.assert_called_once()

    def test_subscribe_user_to_plan_fails_when_user_does_not_have_enough_balance_in_wallet(self):
        with pytest.raises(InsufficientWalletBalance):
            subscribe(self.user, self.plan.id, Decimal('30000'))

        assert UserPlan.objects.filter(user=self.user, plan=self.plan).exists() is False

    def test_subscribe_user_to_plan_fails_when_amount_is_less_than_zero(self):
        with pytest.raises(InvalidAmount):
            subscribe(self.user, self.plan.id, Decimal('-11'))

        assert UserPlan.objects.filter(user=self.user, plan=self.plan).exists() is False

    def test_subscribe_user_to_plan_fails_when_amount_is_less_than_plan_min_staking_amount(self):
        with pytest.raises(InvalidAmount):
            subscribe(self.user, self.plan.id, Decimal('4.9'))

        assert UserPlan.objects.filter(user=self.user, plan=self.plan).exists() is False

    def test_subscribe_user_to_plan_fails_when_plan_has_lower_capacity(self):
        self.plan.filled_capacity += self.plan.total_capacity - Decimal('89.9')
        self.plan.save(update_fields=['filled_capacity'])
        with pytest.raises(LowPlanCapacity):
            subscribe(self.user, self.plan.id, Decimal('90'))

        assert UserPlan.objects.filter(user=self.user, plan=self.plan).exists() is False

    def test_subscribe_user_to_plan_fails_when_plan_is_not_yet_open_to_accept_request(self):
        self.plan.opened_at = ir_now() + timedelta(days=2)
        self.plan.save(
            update_fields=('opened_at',),
        )

        with pytest.raises(TooSoon):
            subscribe(self.user, self.plan.id, Decimal('190'))

        assert UserPlan.objects.filter(user=self.user, plan=self.plan).exists() is False

    def test_subscribe_user_to_plan_fails_when_it_is_after_plan_request_period(self):
        self.plan.opened_at -= timedelta(days=4)
        self.plan.save(
            update_fields=('opened_at',),
        )

        with pytest.raises(TooLate):
            subscribe(self.user, self.plan.id, Decimal('13'))

        assert UserPlan.objects.filter(user=self.user, plan=self.plan).exists() is False

    @patch('exchange.staking.errors.report_exception')
    def test_subscribe_user_to_plan_fails_when_admin_rejected_user_recent_request(self, mocked_report_exception):
        user_plan = UserPlan.objects.create(
            user=self.user,
            plan=self.plan,
            status=UserPlan.Status.REQUESTED,
            requested_amount=Decimal('12.11'),
            locked_amount=Decimal('12.11'),
        )
        UserPlanRequest.objects.create(
            user_plan=user_plan,
            tp=UserPlanRequest.Type.SUBSCRIPTION,
            status=UserPlanRequest.Status.ADMIN_REJECTED,
            amount=Decimal('1.13'),
        )

        subscribe(self.user, self.plan.id, Decimal('9.5'))

        assert UserPlan.objects.filter(
            user=self.user,
            plan=self.plan,
            status=UserPlan.Status.REQUESTED,
            requested_amount=Decimal('12.11'),
            locked_amount=Decimal('12.11'),
        )
        assert UserPlanRequest.objects.filter(amount=Decimal('9.5'), user_plan=user_plan).exists() is False
        mocked_report_exception.assert_called_once()

    @patch('exchange.staking.errors.report_exception')
    def test_subscribe_user_to_plan_fails_when_user_canceled_recent_request(self, mocked_report_exception):
        user_plan = UserPlan.objects.create(
            user=self.user,
            plan=self.plan,
            status=UserPlan.Status.REQUESTED,
            requested_amount=Decimal('121.3'),
            locked_amount=Decimal('121.3'),
        )
        UserPlanRequest.objects.create(
            user_plan=user_plan,
            tp=UserPlanRequest.Type.SUBSCRIPTION,
            status=UserPlanRequest.Status.USER_CANCELLED,
            amount=Decimal('2'),
        )

        subscribe(self.user, self.plan.id, Decimal('19.5'))

        assert UserPlan.objects.filter(
            user=self.user,
            plan=self.plan,
            status=UserPlan.Status.REQUESTED,
            requested_amount=Decimal('121.3'),
            locked_amount=Decimal('121.3'),
        )
        assert UserPlanRequest.objects.filter(amount=Decimal('19.5'), user_plan=user_plan).exists() is False
        mocked_report_exception.assert_called_once()

    @patch('exchange.staking.errors.report_exception')
    def test_subscribe_user_to_plan_fails_when_user_plan_is_nether_extended_or_requested(self, mocked_report_exception):
        user_plan = UserPlan.objects.create(
            user=self.user,
            plan=self.plan,
            status=UserPlan.Status.LOCKED,
            requested_amount=Decimal('0.0'),
            locked_amount=Decimal('13.11'),
        )

        subscribe(self.user, self.plan.id, Decimal('119.5'))

        assert UserPlan.objects.filter(
            user=self.user,
            plan=self.plan,
            status=UserPlan.Status.LOCKED,
            requested_amount=Decimal('0.0'),
            locked_amount=Decimal('13.11'),
        )
        assert UserPlanRequest.objects.filter(amount=Decimal('119.5'), user_plan=user_plan).exists() is False
        mocked_report_exception.assert_called_once()
