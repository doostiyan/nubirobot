from decimal import Decimal
from unittest.mock import call, patch

from django.test import TestCase

from exchange.staking.models import StakingTransaction
from exchange.staking.tasks import end_users_staking_task
from tests.staking.utils import StakingTestDataMixin


class EndUserStakingTaskTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan1 = self.create_plan(**self.get_plan_kwargs())
        self.plan2 = self.create_plan(**self.get_plan_kwargs())
        self.user1 = self.create_user()
        self.user2 = self.create_user()
        self.user3 = self.create_user()
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake, plan=self.plan1, user=self.user1, amount=Decimal('112')
        )
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake, plan=self.plan2, user=self.user2, amount=Decimal('13')
        )
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake, plan=self.plan2, user=self.user3, amount=Decimal('14')
        )

    @patch('exchange.staking.service.end_staking.end_user_staking')
    def test_end_staking_success(self, mocked_end_staking):
        end_users_staking_task(plan_id=self.plan1.id)
        mocked_end_staking.assert_called_with(self.user1.id, self.plan1.id)

        end_users_staking_task(self.plan2.id)
        mocked_end_staking.assert_has_calls(
            [call(self.user2.id, self.plan2.id), call(self.user3.id, self.plan2.id)], any_order=True
        )
