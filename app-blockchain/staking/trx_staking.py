from exchange.blockchain.api.trx.tronscan import TronscanAPI
from exchange.blockchain.staking.base_staking import BaseStaking
from exchange.blockchain.staking.staking_models import StakingInfo


class TrxStaking(BaseStaking):

    @classmethod
    def get_staking_info(cls, address, start_reward_period=None, end_reward_period=None):
        staking_info = TronscanAPI.get_api().get_staking_info(address)
        return StakingInfo(
            address=address,
            total_balance=staking_info.get('staked_balance') + staking_info.get('balance'),
            staked_balance=staking_info.get('staked_balance'),
            rewards_balance=staking_info.get('reward'),
            free_balance=staking_info.get('balance')
        )
