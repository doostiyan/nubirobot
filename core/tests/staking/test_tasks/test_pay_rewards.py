from decimal import Decimal
from unittest.mock import call, patch

from django.test import TestCase

from exchange.staking.models import StakingTransaction
from exchange.staking.tasks import pay_rewards_task
from tests.staking.utils import StakingTestDataMixin


class PayRewardsTaskTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan1 = self.create_plan(**self.get_plan_kwargs())
        self.plan2 = self.create_plan(**self.get_plan_kwargs())
        self.user1 = self.create_user()
        self.user2 = self.create_user()
        self.user3 = self.create_user()
        self.user4 = self.create_user()
        self.user5 = self.create_user()

        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake, plan=self.plan1, user=self.user1, amount=Decimal('12')
        )

        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake, plan=self.plan1, user=self.user2, amount=Decimal('0.0')
        )
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake, plan=self.plan1, user=self.user3, amount=Decimal('3.0')
        )
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.give_reward, plan=self.plan1, user=self.user3, amount=Decimal('1.0')
        )

        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake, plan=self.plan2, user=self.user4, amount=Decimal('13')
        )

    @patch('exchange.staking.service.pay_rewards._pay_user_reward')
    def test_pay_rewards_task_calls_pay_reward_service_successfully(self, mocked_pay_reward_service):
        pay_rewards_task(self.plan1.id)
        mocked_pay_reward_service.assert_called_once_with(self.user1.id, self.plan1.id)

    @patch('exchange.staking.service.pay_rewards._pay_user_reward')
    def test_pay_reward_task_calls_pay_reward_service_when_multiple_users_exist_for_reward_payment(
        self, mocked_pay_reward_service
    ):
        user6 = self.create_user()
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.stake, plan=self.plan1, user=user6, amount=Decimal('13')
        )

        pay_rewards_task(self.plan1.id)

        mocked_pay_reward_service.assert_has_calls(
            [call(self.user1.id, self.plan1.id), call(user6.id, self.plan1.id)], any_order=True
        )
