from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from exchange.staking.tasks import edit_last_announced_reward
from tests.staking.utils import StakingTestDataMixin


class EditLastAnnouncedRewardAdminTaskTest(StakingTestDataMixin, TestCase):
    @patch('exchange.staking.tasks.edit_last_announced_reward_service')
    def test_edit_announce_reward_task_calls_edit_announce_reward_service(self, mocked_edit_announce_reward_service):
        edit_last_announced_reward(plan_id=12345, amount='134.65')

        mocked_edit_announce_reward_service.assert_called_once_with(12345, Decimal('134.65'))
