import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator
from pydantic.alias_generators import to_camel
from pydantic.config import ConfigDict

from exchange.accounts.models import User
from exchange.base.api import ParseError
from exchange.base.normalizers import normalize_mobile


class UTMParams(BaseModel):
    utm_source: str = Field(description='Identifies the source of the traffic.')
    utm_medium: str = Field(description='Describes the marketing medium or channel. ex')
    utm_campaign: str = Field(description='Tracks the specific campaign name, product, or promotion.')

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class CampaignOTPRequest(BaseModel):
    mobile_number: str = Field(description='Mobile number in iranian format')
    utm_params: UTMParams = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    @field_validator('mobile_number')
    @classmethod
    def normalize_mobile(cls, value):
        value = normalize_mobile(value)
        if re.fullmatch(r'^(\+98|0)?9\d{9}$', normalize_mobile(value)):
            return normalize_mobile(value)

        raise ParseError(
            'Invalid mobile number',
        )


class CampaignOTPVerifyRequest(CampaignOTPRequest):
    code: str = Field(description='OTP verification code', min_length=6)


class CampaignRewardCapacitySchema(BaseModel):
    status: str
    details: Dict[str, Any]

    @field_validator('details', mode='before')
    @classmethod
    def camelcase_keys(cls, d):
        return {to_camel(k): v for k, v in d.items()}

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

class CampaignViewSchema(BaseModel):
    status: str
    webengage_id: Optional[str]
    campaign_details: Dict[str, Any]

    @field_validator('campaign_details', mode='before')
    @classmethod
    def camelcase_keys(cls, d):
        return {to_camel(k): v for k, v in d.items()}

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

@dataclass
class UserInfo:
    user_id: int
    webengage_id: str
    mobile_number: str
    level: User.USER_TYPES

    def __init__(self, user_id=None, webengage_id=None, mobile_number=None, level=None):
        self.user_id = user_id
        self.webengage_id = webengage_id
        self.level = level
        self.mobile_number = mobile_number
