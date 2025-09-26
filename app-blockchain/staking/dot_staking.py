from exchange.blockchain.api.dot.subscan import SubscanAPI
from exchange.blockchain.staking.base_staking import BaseStaking


class DotStaking(BaseStaking):

    @classmethod
    def get_staking_info(cls, address, start_reward_period=None, end_reward_period=None):
        api = SubscanAPI.get_api()
        staking_info = api.get_staking_info(address)
        staking_info.address = address
        return staking_info
