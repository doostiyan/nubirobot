from decimal import Decimal
from typing import Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from exchange.accounts.models import User
from exchange.accounts.userstats import UserStatsManager
from exchange.asset_backed_credit.exceptions import ClientError, InternalAPIError
from exchange.asset_backed_credit.externals.base import NOBITEX_BASE_URL, InternalAPI
from exchange.base.decorators import measure_time_cm
from exchange.base.logging import report_event
from exchange.base.models import Settings


class VerificationProfileSchema(BaseModel):
    email_confirmed: bool = False
    mobile_confirmed: bool = False
    identity_confirmed: bool = False
    mobile_identity_confirmed: Optional[bool] = False

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    @field_validator('mobile_identity_confirmed', mode='before')
    @classmethod
    def validate_mobile_identity_confirmed(cls, value: Union[bool, None]) -> bool:
        if value is None:
            return False

        return value


class UserProfileSchema(BaseModel):
    uid: UUID
    username: str
    email: Optional[str] = None
    national_code: Optional[str] = None
    mobile: Optional[str] = None
    verification_status: int
    user_type: int
    verification_profile: VerificationProfileSchema
    gender: int
    birthdate_shamsi: Optional[str] = None
    requires2fa: bool
    father_name: Optional[str] = None

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class UserProvider:
    @staticmethod
    def get_user_fee(user: User) -> Decimal:
        return UserStatsManager.get_user_fee(user, is_maker=True)

    @classmethod
    def get_user(cls, user_id: UUID) -> UserProfileSchema:
        if Settings.get_flag('abc_use_internal_user_profile_api'):
            return UserProfileAPI().request(user_id=user_id)
        return cls._get_user(user_id)

    @classmethod
    def _get_user(cls, user_id: UUID) -> UserProfileSchema:
        user = User.objects.select_related('verification_profile').get(uid=user_id)
        verification_profile = user.get_verification_profile()
        return UserProfileSchema(
            uid=user.uid,
            username=user.username,
            email=user.email,
            national_code=user.national_code,
            mobile=user.mobile,
            verification_status=user.verification_status,
            user_type=user.user_type,
            verification_profile=VerificationProfileSchema(
                email_confirmed=verification_profile.email_confirmed,
                mobile_confirmed=verification_profile.mobile_confirmed,
                identity_confirmed=verification_profile.identity_confirmed,
                mobile_identity_confirmed=verification_profile.mobile_identity_confirmed,
            ),
            gender=user.gender,
            birthdate_shamsi=user.birthday_shamsi,
            requires2fa=user.requires_2fa,
            father_name=user.father_name,
        )

class UserProfileAPI(InternalAPI):
    url = NOBITEX_BASE_URL + '/internal/users/%s/profile'
    method = 'get'
    need_auth = True
    service_name = 'account'
    endpoint_key = 'userProfile'
    error_message = 'AccountUserProfile'

    @measure_time_cm(metric='abc_account_userProfile')
    def request(self, user_id: UUID) -> UserProfileSchema:
        self.url = self.url % user_id
        try:
            api_result = self._request()
        except (ValueError, ClientError) as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise InternalAPIError(f'{self.error_message}: Fail to connect server') from e

        return UserProfileSchema.model_validate(api_result.json())
