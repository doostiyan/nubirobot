from abc import ABC, abstractmethod


class BaseStaking(ABC):
    @classmethod
    @abstractmethod
    def get_staking_info(cls, address, start_reward_period=None, end_reward_period=None):
        pass

    @classmethod
    def get_staked_balance(cls, address):
        pass

    @classmethod
    def get_total_balance(cls, address):
        pass

    @classmethod
    def get_rewards_balance(cls, address):
        pass

    @classmethod
    def get_free_balance(cls, address):
        pass

    @classmethod
    def get_delegated_balance(cls, address):
        pass

    @classmethod
    def get_pending_rewards(cls, address):
        pass

    @classmethod
    def get_end_date(cls):
        pass
