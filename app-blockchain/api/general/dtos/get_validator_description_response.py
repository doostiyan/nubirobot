from typing import Optional

from pydantic import BaseModel


class GetValidatorDescriptionResponse(BaseModel):
    validator_name: str
    website: Optional[str]
