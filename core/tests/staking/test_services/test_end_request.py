from decimal import Decimal

import pytest
from django.test import TestCase

from exchange.staking.errors import InvalidAmount, NonExtendablePlan, ParentIsNotCreated
from exchange.staking.models import Plan, StakingTransaction
from exchange.staking.service.v1.end_request import create_end_request

from ..utils import StakingTestDataMixin


class EndRequestServiceTest(StakingTestDataMixin, TestCase):

    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = self.create_user()
        self.create_staking_transaction(StakingTransaction.TYPES.stake, Decimal('193'), user=self.user, plan=self.plan)

    def assert_end_request_staking_transaction(self, amount: Decimal, plan: Plan = None):
        plan = plan or self.plan
        assert StakingTransaction.objects.get(
            tp=StakingTransaction.TYPES.end_request,
            amount=amount,
            user=self.user,
            plan=plan,
        )

    def test_create_request_successfully(self):
        create_end_request(user_id=self.user.id, plan_id=self.plan.id, amount=Decimal('12.4'))

        self.assert_end_request_staking_transaction(Decimal('12.4'))

    def test_create_end_request_multiple_times_sums_all_amounts(self):
        create_end_request(user_id=self.user.id, plan_id=self.plan.id, amount=Decimal('1'))
        self.assert_end_request_staking_transaction(Decimal('1'))

        create_end_request(user_id=self.user.id, plan_id=self.plan.id, amount=Decimal('1.5'))
        self.assert_end_request_staking_transaction(Decimal('1') + Decimal('1.5'))

        create_end_request(user_id=self.user.id, plan_id=self.plan.id, amount=Decimal('2.5'))
        self.assert_end_request_staking_transaction(Decimal('1') + Decimal('1.5') + Decimal('2.5'))

    def test_when_user_has_no_staking_in_plan_then_error_is_raised(self):
        plan = self.create_plan(**self.get_plan_kwargs())

        with pytest.raises(ParentIsNotCreated):
            create_end_request(user_id=self.user.id, plan_id=plan.id, amount=Decimal('6.1'))

        assert StakingTransaction.objects.filter(user=self.user, plan=plan).exists() is False

    def test_when_end_request_amount_is_more_than_user_staked_amount_then_error_is_raised(self):
        with pytest.raises(InvalidAmount) as e:
            create_end_request(user_id=self.user.id, plan_id=self.plan.id, amount=Decimal('193.1'))

        assert e.value.message == f"Amount is not acceptable. (plan_id: '{self.plan.id}')"
        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.end_request, user=self.user, plan=self.plan
            ).exists()
            is False
        )

    def test_when_call_end_request_multiple_times_and_last_request_exceeds_from_user_staked_amount_then_error_is_raised(
        self,
    ):
        create_end_request(user_id=self.user.id, plan_id=self.plan.id, amount=Decimal('93'))
        self.assert_end_request_staking_transaction(Decimal('93'))

        with pytest.raises(InvalidAmount) as e:
            create_end_request(user_id=self.user.id, plan_id=self.plan.id, amount=Decimal('100.1'))
        assert e.value.message == f"Amount is not acceptable. (plan_id: '{self.plan.id}')"
        assert (
            StakingTransaction.objects.filter(
                amount__gt=Decimal('93'), tp=StakingTransaction.TYPES.end_request, user=self.user, plan=self.plan
            ).exists()
            is False
        )

    def test_when_end_request_amount_reduces_user_staked_amount_less_than_plan_min_stake_amount_then_error_is_raised(
        self,
    ):
        self.plan.min_staking_amount = Decimal('99')
        self.plan.save(update_fields=['min_staking_amount'])

        with pytest.raises(InvalidAmount) as e:
            create_end_request(user_id=self.user.id, plan_id=self.plan.id, amount=Decimal('94.1'))
        assert e.value.message == f"Amount is not acceptable. (plan_id: '{self.plan.id}')"
        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.end_request, user=self.user, plan=self.plan
            ).exists()
            is False
        )

    def test_when_call_end_request_multiple_times_but_the_last_request_reduces_user_staked_amount_less_than_plan_min_stake_amount_then_error_is_raised(
        self,
    ):
        self.plan.min_staking_amount = Decimal('99.1')
        self.plan.save(update_fields=['min_staking_amount'])

        create_end_request(user_id=self.user.id, plan_id=self.plan.id, amount=Decimal('2.1'))
        self.assert_end_request_staking_transaction(Decimal('2.1'))

        with pytest.raises(InvalidAmount) as e:
            create_end_request(user_id=self.user.id, plan_id=self.plan.id, amount=Decimal('92.1'))
        assert e.value.message == f"Amount is not acceptable. (plan_id: '{self.plan.id}')"
        assert (
            StakingTransaction.objects.filter(
                amount__gt=Decimal('2.1'), tp=StakingTransaction.TYPES.end_request, user=self.user, plan=self.plan
            ).exists()
            is False
        )

    def test_end_all_staked_amount_successfully(self):
        create_end_request(user_id=self.user.id, plan_id=self.plan.id, amount=Decimal('193'))
        self.assert_end_request_staking_transaction(Decimal('193'))

    def test_end_all_staked_amount_with_multiple_end_requests_successfully(self):
        create_end_request(user_id=self.user.id, plan_id=self.plan.id, amount=Decimal('91'))
        self.assert_end_request_staking_transaction(Decimal('91'))

        create_end_request(user_id=self.user.id, plan_id=self.plan.id, amount=Decimal('102'))
        self.assert_end_request_staking_transaction(Decimal('193'))

    def test_when_plan_is_not_extendable_then_error_is_raised(self):
        self.plan.is_extendable = False
        self.plan.save(update_fields=['is_extendable'])

        with pytest.raises(NonExtendablePlan) as e:
            create_end_request(user_id=self.user.id, plan_id=self.plan.id, amount=Decimal('10'))

        assert e.value.message == f"Plan is not extendable."
        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.end_request, user=self.user, plan=self.plan
            ).exists()
            is False
        )

    def test_when_amount_is_less_than_zero_then_error_is_raised(self):
        with pytest.raises(InvalidAmount) as e:
            create_end_request(user_id=self.user.id, plan_id=self.plan.id, amount=Decimal('-10'))

        assert e.value.message == f"Amount should be positive."
        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.end_request, user=self.user, plan=self.plan
            ).exists()
            is False
        )
