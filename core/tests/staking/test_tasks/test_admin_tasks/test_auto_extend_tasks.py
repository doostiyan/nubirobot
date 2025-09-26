from unittest.mock import patch

from django.test import TestCase

from exchange.staking.tasks import disable_auto_extend_task, enable_auto_extend_task
from tests.staking.utils import StakingTestDataMixin


class EnableAutoExtendTaskTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = self.create_user()

    @patch('exchange.staking.service.auto_renewal._set_user_plan_auto_renewal')
    @patch('exchange.staking.models.StakingTransaction.disable_auto_end')
    def test_task_successfully_calls_disable_auto_end_and_user_plan_renewal_services(
        self, mocked_disable_auto_end, mocked_set_user_plan_auto_renewal
    ):
        enable_auto_extend_task(plan_id=self.plan.id, user_id=self.user.id)

        mocked_disable_auto_end.assert_called_once_with(self.user.id, self.plan.id)
        mocked_set_user_plan_auto_renewal.assert_called_once_with(
            plan_id=self.plan.id, user_id=self.user.id, allow_renewal=True
        )


class DisableAutoExtendTaskTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = self.create_user()

    @patch('exchange.staking.service.auto_renewal._set_user_plan_auto_renewal')
    @patch('exchange.staking.models.StakingTransaction.enable_auto_end')
    def test_task_successfully_calls_enable_auto_end_and_user_plan_renewal_services(
        self, mocked_enable_auto_end, mocked_set_user_plan_auto_renewal
    ):
        disable_auto_extend_task(plan_id=self.plan.id, user_id=self.user.id)

        mocked_enable_auto_end.assert_called_once_with(self.user.id, self.plan.id)
        mocked_set_user_plan_auto_renewal.assert_called_once_with(
            plan_id=self.plan.id, user_id=self.user.id, allow_renewal=False
        )
