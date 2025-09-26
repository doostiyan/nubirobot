"""Best Performing Plan Tests"""
import decimal
import typing

from django.test import TestCase

from exchange.base.calendar import ir_now
from exchange.staking import best_performing_plans
from exchange.staking.models import Plan, PlanTransaction, ExternalEarningPlatform

from .utils import PlanTestDataMixin


class OfferedPlansSelectionTest(PlanTestDataMixin, TestCase):

    def create_plans(
        self,
        currency: int,
        given_rewards: decimal.Decimal,
        tp: typing.Optional[int] = ExternalEarningPlatform.TYPES.staking,
    ):
        external_earning = ExternalEarningPlatform.objects.create(
            tp=tp,
            currency=currency,
            network='network',
            address='address',
            tag='tag',
        )
        plan_kwargs = self.get_plan_kwargs(external_earning)
        plan_kwargs['staked_at'] = ir_now() - plan_kwargs['staking_period']
        extended_from_plan = Plan.objects.create(**plan_kwargs)
        announce_rewards_transaction = PlanTransaction.objects.create(
            plan=extended_from_plan,
            tp=PlanTransaction.TYPES.announce_reward,
            amount=given_rewards,
        )
        PlanTransaction.objects.create(
            plan=extended_from_plan,
            parent=announce_rewards_transaction,
            tp=PlanTransaction.TYPES.give_reward,
        )
        plan_kwargs = self.get_plan_kwargs(external_earning)
        plan_kwargs['extended_from'] = extended_from_plan
        Plan.objects.create(**plan_kwargs)  # active plan

    def test_select_best_performing_plans(self):
        self.create_plans(1, decimal.Decimal('10'))
        self.create_plans(2, decimal.Decimal('11'))
        self.create_plans(3, decimal.Decimal('9'))
        self.create_plans(4, decimal.Decimal('20'))
        self.create_plans(4, decimal.Decimal('19'))
        self.create_plans(5, decimal.Decimal('7'))
        self.create_plans(6, decimal.Decimal('6'))
        self.create_plans(100, decimal.Decimal('10000'), ExternalEarningPlatform.TYPES.yield_aggregator)
        best_performings = best_performing_plans._select_best_performing_plans(
            ExternalEarningPlatform.TYPES.staking,
        )
        assert [plan.currency for plan in best_performings] == [4, 2, 1, 3]
