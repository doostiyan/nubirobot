from decimal import Decimal
from typing import List

from pydantic import BaseModel

from exchange.blockchain.api.general.dtos.validator_status import ValidatorStatus


class ValidatorInfo(BaseModel):
    address: str
    website: str
    name: str
    status: ValidatorStatus
    total_staked: Decimal
    commission_rate: Decimal
    annual_effective_reward_rate: Decimal


class GetAllValidatorsResponse(BaseModel):
    validators: List[ValidatorInfo]
    base_reward_rate: Decimal
