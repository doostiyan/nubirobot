from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import TestCase

from exchange.staking import errors
from exchange.staking.errors import InvalidAmount
from exchange.staking.models import ExternalEarningPlatform, StakingTransaction
from exchange.staking.service.reject_requests.subscription import reject_user_subscription
from exchange.staking.models import ExternalEarningPlatform, Plan, StakingTransaction
from tests.staking.utils import StakingTestDataMixin


class RejectCreateRequestTest(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.plan.filled_capacity = Decimal('1000')
        self.plan.total_capacity = Decimal('1000')
        self.plan.save()
        self.user = self.create_user()
        self.create_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.create_request, amount=Decimal('20'), user=self.user, plan=self.plan
        )

    def test_reject_total_create_request_successfully(self):
        admin_rejected_transaction = reject_user_subscription(
            user_id=self.user.id,
            plan_id=self.plan.id,
            amount=Decimal('20'),
        )

        assert admin_rejected_transaction.tp == StakingTransaction.TYPES.admin_rejected_create
        assert admin_rejected_transaction.amount == Decimal('20')
        assert admin_rejected_transaction.parent == self.create_request
        assert admin_rejected_transaction.wallet_transaction
        assert admin_rejected_transaction.wallet_transaction.amount == Decimal('20')
        assert not StakingTransaction.objects.filter(
            parent=self.create_request, tp=StakingTransaction.TYPES.create_request, amount__gt=0
        ).exists()
        self.plan.refresh_from_db(fields=['filled_capacity'])
        assert self.plan.filled_capacity == Decimal('980')

    def test_reject_total_create_request_successfully_for_yield_farming_plan(self):
        yield_plan = self.create_plan(
            **self.get_plan_kwargs(
                self.add_external_platform(currency=30, tp=ExternalEarningPlatform.TYPES.yield_aggregator)
            )
        )
        yield_plan.filled_capacity = Decimal('1000')
        yield_plan.total_capacity = Decimal('1000')
        yield_plan.save()
        create_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.create_request,
            amount=Decimal('300'),
            user=self.user,
            plan=yield_plan,
        )
        admin_rejected_transaction = reject_user_subscription(
            user_id=self.user.id,
            plan_id=yield_plan.id,
            amount=Decimal('100'),
        )

        assert admin_rejected_transaction.tp == StakingTransaction.TYPES.admin_rejected_create
        assert admin_rejected_transaction.amount == Decimal('100')
        assert admin_rejected_transaction.parent == create_request
        assert admin_rejected_transaction.wallet_transaction
        assert admin_rejected_transaction.wallet_transaction.amount == Decimal('100')
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=yield_plan,
            tp=StakingTransaction.TYPES.create_request,
            parent=create_request,
            amount=Decimal('200'),
        )
        yield_plan.refresh_from_db(fields=['filled_capacity'])
        assert yield_plan.filled_capacity == Decimal('900')

    def test_partial_reject_successfully_and_recreate_remaining_as_new_request(self):
        admin_rejected_transaction = reject_user_subscription(
            user_id=self.user.id,
            plan_id=self.plan.id,
            amount=Decimal('5.5'),
        )

        assert admin_rejected_transaction.tp == StakingTransaction.TYPES.admin_rejected_create
        assert admin_rejected_transaction.amount == Decimal('5.5')
        assert admin_rejected_transaction.parent == self.create_request
        assert admin_rejected_transaction.wallet_transaction
        assert admin_rejected_transaction.wallet_transaction.amount == Decimal('5.5')
        assert StakingTransaction.objects.get(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.create_request,
            parent=self.create_request,
            amount=Decimal('14.5'),
        )
        self.plan.refresh_from_db(fields=['filled_capacity'])
        assert self.plan.filled_capacity == Decimal('994.5')

    def test_when_create_request_does_not_exist_then_parent_is_none_and_reject_transaction_amount_zero(self):
        self.create_request.delete()
        with pytest.raises(InvalidAmount):
            reject_user_subscription(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('10.0'),
            )

        assert (
            StakingTransaction.objects.filter(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('10'),
                tp=StakingTransaction.TYPES.admin_rejected_create,
            ).exists()
            == False
        )

    def test_when_amount_is_below_plan_minimum_staking_amount_then_raises_invalid_amount(self):
        self.plan.min_staking_amount = Decimal('10')
        self.plan.save(update_fields=['min_staking_amount'])

        with pytest.raises(errors.InvalidAmount):
            reject_user_subscription(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('5.1'),
            )

        assert StakingTransaction.objects.get(
            user_id=self.user.id,
            plan_id=self.plan.id,
            amount=Decimal('20'),
            tp=StakingTransaction.TYPES.create_request,
            parent__isnull=True,
        )
        assert (
            StakingTransaction.objects.filter(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('15.1'),
                tp=StakingTransaction.TYPES.admin_rejected_create,
            ).exists()
            == False
        )

    def test_when_amount_is_negative_then_raises_invalid_amount(self):
        with pytest.raises(errors.InvalidAmount):
            reject_user_subscription(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('-1'),
            )

        assert StakingTransaction.objects.get(
            user_id=self.user.id,
            plan_id=self.plan.id,
            amount=Decimal('20'),
            tp=StakingTransaction.TYPES.create_request,
            parent__isnull=True,
        )
        assert (
            StakingTransaction.objects.filter(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount__lte=0,
                tp=StakingTransaction.TYPES.admin_rejected_create,
            ).exists()
            == False
        )

    @patch('exchange.staking.service.reject_requests.subscription.create_and_commit_transaction')
    def test_when_wallet_transfer_function_raises_error_then_no_reject_happens(self, mocked_wallet_transfer):
        mocked_wallet_transfer.side_effect = ValueError

        with pytest.raises(errors.FailedAssetTransfer):
            reject_user_subscription(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('10'),
            )

        assert StakingTransaction.objects.get(
            user_id=self.user.id,
            plan_id=self.plan.id,
            amount=Decimal('20'),
            tp=StakingTransaction.TYPES.create_request,
            parent__isnull=True,
        )
        assert (
            StakingTransaction.objects.filter(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('10'),
                tp=StakingTransaction.TYPES.admin_rejected_create,
            ).exists()
            == False
        )


class RejectEndRequestTest(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.plan.total_capacity = Decimal('1000')
        self.plan.filled_capacity = Decimal('400')
        self.plan.save()

        self.user = self.create_user()
        self.stake_transaction = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake,
            amount=Decimal('300'),
            user=self.user,
            plan=self.plan,
        )
        self.instant_end_request = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.instant_end_request,
            amount=Decimal('30'),
            user=self.user,
            plan=self.plan,
        )
        self.unstake_transaction = self.create_staking_transaction(
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('30'),
            user=self.user,
            plan=self.plan,
            parent=self.instant_end_request,
        )

    def test_reject_total_instant_end_request_successfully(self):
        reject_transaction = StakingTransaction._cancel_or_reject_end_request(
            user_id=self.user.id,
            plan_id=self.plan.id,
            amount=Decimal('30'),
            tp=StakingTransaction.TYPES.admin_rejected_end,
        )

        assert reject_transaction.tp == StakingTransaction.TYPES.admin_rejected_end
        assert reject_transaction.amount == Decimal('30')
        assert reject_transaction.parent == self.unstake_transaction

        self.unstake_transaction.refresh_from_db(fields=['amount'])
        assert self.unstake_transaction.amount == Decimal('0.0')

        self.plan.refresh_from_db(fields=['filled_capacity'])
        assert self.plan.filled_capacity == Decimal('430')

        self.stake_transaction.refresh_from_db(fields=['amount'])
        assert self.stake_transaction.amount == Decimal('330')

    def test_reject_partial_instant_end_raises_error(self):
        with pytest.raises(errors.ParentIsNotCreated):
            StakingTransaction._cancel_or_reject_end_request(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('10'),
                tp=StakingTransaction.TYPES.admin_rejected_end,
            )

        assert (
            StakingTransaction.objects.filter(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('10'),
                tp=StakingTransaction.TYPES.admin_rejected_end,
            ).exists()
            == False
        )
        self.unstake_transaction.refresh_from_db(fields=['amount'])
        assert self.unstake_transaction.amount == Decimal('30')

        self.plan.refresh_from_db(fields=['filled_capacity'])
        assert self.plan.filled_capacity == Decimal('400')

        self.stake_transaction.refresh_from_db(fields=['amount'])
        assert self.stake_transaction.amount == Decimal('300')

    def test_when_no_instant_end_request_exists_then_error_is_raised(self):
        self.unstake_transaction.delete()

        with pytest.raises(errors.ParentIsNotCreated):
            StakingTransaction._cancel_or_reject_end_request(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('11'),
                tp=StakingTransaction.TYPES.admin_rejected_end,
            )

        assert (
            StakingTransaction.objects.filter(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('11'),
                tp=StakingTransaction.TYPES.admin_rejected_end,
            ).exists()
            == False
        )
        self.plan.refresh_from_db(fields=['filled_capacity'])
        assert self.plan.filled_capacity == Decimal('400')

        self.stake_transaction.refresh_from_db(fields=['amount'])
        assert self.stake_transaction.amount == Decimal('300')

    def test_when_amount_exceeds_instant_end_request_then_error_is_raised(self):
        with pytest.raises(errors.ParentIsNotCreated):
            StakingTransaction._cancel_or_reject_end_request(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('500'),
                tp=StakingTransaction.TYPES.admin_rejected_end,
            )

        assert (
            StakingTransaction.objects.filter(
                user_id=self.user.id,
                plan_id=self.plan.id,
                tp=StakingTransaction.TYPES.admin_rejected_end,
            ).exists()
            == False
        )
        self.unstake_transaction.refresh_from_db(fields=['amount'])
        assert self.unstake_transaction.amount == Decimal('30')

        self.plan.refresh_from_db(fields=['filled_capacity'])
        assert self.plan.filled_capacity == Decimal('400')

        self.stake_transaction.refresh_from_db(fields=['amount'])
        assert self.stake_transaction.amount == Decimal('300')

    def test_when_plan_has_no_enough_capacity_to_fill_then_error_is_raised(self):
        self.plan.filled_capacity = Decimal('970.5')
        self.plan.save(update_fields=['filled_capacity'])

        with pytest.raises(errors.LowPlanCapacity):
            StakingTransaction._cancel_or_reject_end_request(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('30'),
                tp=StakingTransaction.TYPES.admin_rejected_end,
            )

        assert (
            StakingTransaction.objects.filter(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('30'),
                tp=StakingTransaction.TYPES.admin_rejected_end,
            ).exists()
            == False
        )
        self.unstake_transaction.refresh_from_db(fields=['amount'])
        assert self.unstake_transaction.amount == Decimal('30')

        self.plan.refresh_from_db(fields=['filled_capacity'])
        assert self.plan.filled_capacity == Decimal('970.5')

        self.stake_transaction.refresh_from_db(fields=['amount'])
        assert self.stake_transaction.amount == Decimal('300')

    def test_when_amount_is_zero_then_error_is_raised(self):
        with pytest.raises(errors.InvalidAmount):
            StakingTransaction._cancel_or_reject_end_request(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('0.0'),
                tp=StakingTransaction.TYPES.admin_rejected_end,
            )

        assert (
            StakingTransaction.objects.filter(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('0.0'),
                tp=StakingTransaction.TYPES.admin_rejected_end,
            ).exists()
            == False
        )
        self.unstake_transaction.refresh_from_db(fields=['amount'])
        assert self.unstake_transaction.amount == Decimal('30')

        self.plan.refresh_from_db(fields=['filled_capacity'])
        assert self.plan.filled_capacity == Decimal('400')

        self.stake_transaction.refresh_from_db(fields=['amount'])
        assert self.stake_transaction.amount == Decimal('300')

    def test_when_amount_is_less_that_zero_then_error_is_raised(self):
        with pytest.raises(errors.InvalidAmount):
            StakingTransaction._cancel_or_reject_end_request(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('-1'),
                tp=StakingTransaction.TYPES.admin_rejected_end,
            )

        assert (
            StakingTransaction.objects.filter(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('-1'),
                tp=StakingTransaction.TYPES.admin_rejected_end,
            ).exists()
            == False
        )
        self.unstake_transaction.refresh_from_db(fields=['amount'])
        assert self.unstake_transaction.amount == Decimal('30')

        self.plan.refresh_from_db(fields=['filled_capacity'])
        assert self.plan.filled_capacity == Decimal('400')

        self.stake_transaction.refresh_from_db(fields=['amount'])
        assert self.stake_transaction.amount == Decimal('300')

    def test_when_plan_id_is_invalid_then_error_is_raised(self):
        plan_id = Plan.objects.latest('id').id + 100
        with pytest.raises(errors.ParentIsNotCreated):
            StakingTransaction._cancel_or_reject_end_request(
                user_id=self.user.id,
                plan_id=plan_id,
                amount=Decimal('100'),
                tp=StakingTransaction.TYPES.admin_rejected_end,
            )

        assert (
            StakingTransaction.objects.filter(
                user_id=self.user.id,
                plan_id=plan_id,
                tp=StakingTransaction.TYPES.admin_rejected_end,
            ).exists()
            == False
        )

    def test_when_user_has_no_staking_in_plan_then_error_is_raised(self):
        self.stake_transaction.delete()
        with pytest.raises(errors.ParentIsNotCreated):
            StakingTransaction._cancel_or_reject_end_request(
                user_id=self.user.id,
                plan_id=self.plan.id,
                amount=Decimal('100'),
                tp=StakingTransaction.TYPES.admin_rejected_end,
            )

        assert (
            StakingTransaction.objects.filter(
                user_id=self.user.id,
                plan_id=self.plan.id,
                tp=StakingTransaction.TYPES.admin_rejected_end,
            ).exists()
            == False
        )
