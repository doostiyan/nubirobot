from exchange.blockchain.staking.staking_factory import StakingFactory


class StakingInterface:

    @classmethod
    def get_info(cls, network, address, currency=0, platform=None, force_periodical_reward=False,
                 start_reward_period=None, end_reward_period=None):
        staking = StakingFactory.get_staking(network, currency, platform)
        return staking.get_staking_info(address, start_reward_period, end_reward_period)
