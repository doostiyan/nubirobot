from exchange.blockchain.api.bnb.binance import BinanceAPI
from exchange.blockchain.api.bnb.bnbchain import Bnbchain
from exchange.blockchain.staking.base_staking import BaseStaking
from exchange.blockchain.staking.staking_models import StakingInfo, CoinType


class BnbStaking(BaseStaking):
    staking_api = Bnbchain.get_api()
    balance_api = BinanceAPI.get_api()

    @classmethod
    def get_staking_info(cls, address, start_reward_period=None, end_reward_period=None):
        free_balance = cls.get_free_balance(address)
        staked_balance = cls.get_staked_balance(address)
        rewards_balance = cls.staking_api.get_staking_reward(address, start_reward_period, end_reward_period)
        return StakingInfo(
            address=address,
            staked_balance=staked_balance,
            free_balance=free_balance,
            total_balance=free_balance+staked_balance,
            rewards_balance=rewards_balance,
            delegated_balance=staked_balance,
            coin_type=CoinType.PERIODIC_REWARD,
        )

    @classmethod
    def get_free_balance(cls, address):
        free_balance = cls.balance_api.get_balance(address).get(cls.balance_api.currency).get('amount')
        return free_balance

    @classmethod
    def get_staked_balance(cls, address):
        return cls.staking_api.get_delegated_balance(address)
