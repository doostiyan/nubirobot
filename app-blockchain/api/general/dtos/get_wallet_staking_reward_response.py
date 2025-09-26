from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel

from exchange.blockchain.api.general.dtos.get_validator_info_response import ValidatorStatus


class TargetValidator(BaseModel):
    address: str
    name: str
    website: Optional[str]
    status: ValidatorStatus
    commission_rate: Decimal


class GetWalletStakingRewardResponse(BaseModel):
    staked_balance: Decimal
    daily_rewards: Decimal
    reward_rate: Decimal
    target_validators: List[TargetValidator]
