from exchange.blockchain.api.atom.atom_node import AtomAllthatnode
from exchange.blockchain.staking.base_staking import BaseStaking
from exchange.blockchain.staking.staking_models import StakingInfo


class AtomStaking(BaseStaking):

    @classmethod
    def get_staking_info(cls, address, start_reward_period=None, end_reward_period=None):
        api = AtomAllthatnode.get_api()
        free_balance = api.get_balance(address).get(api.currency).get('amount')
        staked_balance = api.get_delegated_balance(address)
        rewards_balance = api.get_staking_reward(address)
        return StakingInfo(
            address=address,
            staked_balance=staked_balance,
            total_balance=free_balance+staked_balance,
            rewards_balance=rewards_balance,
            delegated_balance=staked_balance,
        )
