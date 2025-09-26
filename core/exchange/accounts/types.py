from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class InternalVerificationProfileSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    email_confirmed: bool = False
    mobile_confirmed: bool = False
    identity_confirmed: bool = False
    mobile_identity_confirmed: Optional[bool] = False


class InternalUserProfileSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    uid: UUID
    username: str
    email: Optional[str]
    national_code: Optional[str]
    mobile: Optional[str]
    verification_status: int
    user_type: int
    verification_profile: InternalVerificationProfileSchema
    gender: int
    birthdate_shamsi: Optional[str] = Field(alias='birthday_shamsi', serialization_alias='birthdateShamsi')
    requires_2fa: bool = Field(alias='requires2fa')
    father_name: Optional[str] = None
