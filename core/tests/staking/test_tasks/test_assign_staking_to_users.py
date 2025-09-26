from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from exchange.staking.models import StakingTransaction
from exchange.staking.tasks import assign_staking_to_users_task
from tests.staking.utils import StakingTestDataMixin


class AssignStakingToUsersTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan1 = self.create_plan(**self.get_plan_kwargs())
        self.plan2 = self.create_plan(**self.get_plan_kwargs())
        self.user1 = self.create_user()
        self.user2 = self.create_user()
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake, plan=self.plan1, user=self.user1, amount=Decimal('12')
        )
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake, plan=self.plan2, user=self.user2, amount=Decimal('3')
        )

    @patch('exchange.staking.service.stake_assets.stake_user_assets')
    def test_assign_staking_to_users_success(self, mocked_stake_assets):
        assign_staking_to_users_task(self.plan1.id)
        mocked_stake_assets.assert_called_with(self.user1.id, self.plan1.id)

        assign_staking_to_users_task(self.plan1.id)
        mocked_stake_assets.assert_called_with(self.user1.id, self.plan1.id)
