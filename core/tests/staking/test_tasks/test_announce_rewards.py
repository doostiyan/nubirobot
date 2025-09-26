from unittest.mock import patch

from django.test import TestCase

from exchange.staking.tasks import announce_rewards_task
from tests.staking.utils import StakingTestDataMixin


class AnnounceRewardsTaskTests(StakingTestDataMixin, TestCase):
    @patch('exchange.staking.tasks.announce_all_users_rewards')
    def test_announce_rewards_task_calls_announce_rewards_service_successfully(self, mocked_reward_service):
        announce_rewards_task(12345)

        mocked_reward_service.assert_called_once_with(12345)
