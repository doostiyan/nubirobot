from exchange.blockchain.api.ftm.ftm_graphql import FantomGraphQlAPI
from exchange.blockchain.staking.base_staking import BaseStaking


class FtmStaking(BaseStaking):

    @classmethod
    def get_staking_info(cls, address, start_reward_period=None, end_reward_period=None):
        api = FantomGraphQlAPI.get_api()
        staking_info = api.get_staking_info(address)
        if not staking_info:
            return None
        return staking_info
