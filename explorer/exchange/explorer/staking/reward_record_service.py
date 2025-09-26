import logging

from django.utils import timezone

from exchange.blockchain.api.general.dtos.get_wallet_staking_reward_response import GetWalletStakingRewardResponse
from exchange.explorer.staking.models import StakingReward

logger = logging.getLogger(__name__)


class RewardRecordService:
    @staticmethod
    def save_daily_reward(
            wallet_address: str,
            network: str,
            reward_response: GetWalletStakingRewardResponse
    ) -> None:
        validator_data = []

        for v in reward_response.target_validators:
            validator = {
                'address': getattr(v, 'address', None),
                'moniker': getattr(v, 'name', None),
                'commission_rate': str(getattr(v, 'commission_rate', None)),
                'status': getattr(v, 'status', None)
            }
            if all(validator.values()):
                validator_data.append(validator)
            else:
                logger.warning('Incomplete validator data found: %s', validator)

        StakingReward.objects.update_or_create(
            wallet_address=wallet_address,
            network=network.upper(),
            reward_date=timezone.now().date(),
            defaults={
                'staked_amount': reward_response.staked_balance,
                'reward_amount': reward_response.daily_rewards,
                'reward_rate': reward_response.reward_rate,
                'validators': validator_data
            }
        )
