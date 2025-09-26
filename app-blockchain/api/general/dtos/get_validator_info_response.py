from pydantic import BaseModel, Field

from exchange.blockchain.api.general.dtos.validator_status import ValidatorStatus


class GetValidatorInfoResponse(BaseModel):
    status: ValidatorStatus = Field(strict=True)
    jail_until: str
    created_time: str
