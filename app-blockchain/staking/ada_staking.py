from exchange.blockchain.api.ada.cardano_graphql import CardanoAPI
from exchange.blockchain.staking.base_staking import BaseStaking
from exchange.blockchain.staking.staking_models import CoinType


class AdaStaking(BaseStaking):

    @classmethod
    def get_staking_info(cls, address, start_reward_period=None, end_reward_period=None):
        api = CardanoAPI.get_api()
        staking_info = api.get_staking_info(address, start_reward_period, end_reward_period)
        staking_info.address = address
        staking_info.total_balance = staking_info.staked_balance
        staking_info.coin_type = CoinType.PERIODIC_REWARD
        return staking_info
