from decimal import Decimal
from unittest.mock import call, patch

from django.test import TestCase

from exchange.staking.models import StakingTransaction
from exchange.staking.tasks import assign_staking_to_users_task, extend_stakings_task
from tests.staking.utils import StakingTestDataMixin


class ExtendStakingTaskTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan1 = self.create_plan(**self.get_plan_kwargs())
        self.plan2 = self.create_plan(**self.get_plan_kwargs())
        self.user1 = self.create_user()
        self.user2 = self.create_user()
        self.user3 = self.create_user()
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.extend_out, plan=self.plan1, user=self.user1, amount=Decimal('134')
        )
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.extend_out, plan=self.plan2, user=self.user2, amount=Decimal('54')
        )
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.extend_out, plan=self.plan2, user=self.user3, amount=Decimal('309')
        )

    @patch('exchange.staking.service.extend_staking._extend_user_staking')
    def test_extend_users_staking_success(self, mocked_extend_staking_service):
        extend_stakings_task(self.plan1.id)
        mocked_extend_staking_service.assert_called_once_with(self.user1.id, self.plan1.id)

        extend_stakings_task(self.plan2.id)
        mocked_extend_staking_service.assert_has_calls(
            [call(self.user2.id, self.plan2.id), call(self.user3.id, self.plan2.id)], any_order=True
        )
