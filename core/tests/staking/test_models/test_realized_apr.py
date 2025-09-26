from datetime import timedelta
from decimal import Decimal

from django.test import TestCase

from exchange.staking.models import PlanTransaction
from tests.staking.utils import PlanTestDataMixin


class RealizedAPRTests(PlanTestDataMixin, TestCase):
    def setUp(self) -> None:
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.plan.total_capacity = 13_000
        self.plan.staking_period = timedelta(days=15)
        self.plan.save(update_fields=['total_capacity', 'staking_period'])

    def test_calculate_apr_successfully(self):
        announce_reward_transaction = self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.announce_reward,
            amount=Decimal('12'),
        )
        self.create_plan_transaction(
            plan=self.plan,
            tp=PlanTransaction.TYPES.give_reward,
            amount=Decimal('11.5'),
            parent_transaction=announce_reward_transaction,
        )

        apr = self.plan.realized_apr
        assert round(Decimal(apr), 3) == Decimal('2.246')

    def test_calculated_apr_is_zero_when_plan_has_no_announce_reward_transaction(self):
        assert self.plan.realized_apr == Decimal('0.0')
