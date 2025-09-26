from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class CoinType(Enum):
    NON_PERIODIC_REWARD = 0
    PERIODIC_REWARD = 1


@dataclass
class StakingInfo:
    address: str = ''
    total_balance: Decimal = None
    staked_balance: Decimal = None
    rewards_balance: Decimal = None
    free_balance: Decimal = None
    delegated_balance: Decimal = None
    pending_rewards: Decimal = None
    claimed_rewards: Decimal = None
    end_staking_plan: datetime = None
    coin_type: Enum = CoinType.NON_PERIODIC_REWARD
