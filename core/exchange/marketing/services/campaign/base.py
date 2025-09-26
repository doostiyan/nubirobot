from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from exchange.accounts.models import User, UserOTP
from exchange.base.decorators import cached_method
from exchange.base.models import Settings
from exchange.marketing.exceptions import InvalidUserIDException
from exchange.marketing.services.mission.base import BaseMission
from exchange.marketing.services.otp import send_sms_otp, verify_sms_otp
from exchange.marketing.types import UserInfo

CAMPAIGNS_SETTINGS_KEY = 'campaigns'


class CampaignType(Enum):
    REFERRAL = 'referral'
    DISCOUNT = 'discount'
    EXTERNAL_DISCOUNT = 'external_discount'


class UserIdentifierType(Enum):
    EMAIL = 'email'
    MOBILE = 'mobile'
    SYSTEM_USER_ID = 'user_id'
    WEBENGAGE_USER_ID = 'webengage_user_id'


@dataclass
class UserIdentifier:
    id: Any
    type: UserIdentifierType


@dataclass
class UTMParameters:
    utm_source: str
    utm_medium: str
    utm_campaign: str


@dataclass
class UserCampaignInfo:
    user_details: UserInfo
    campaign_details: Dict[str, Any]


@cached_method(timeout=10 * 60)
def get_campaign_settings(campaign_id: str) -> Dict[str, Any]:
    return Settings.get_dict(f'{CAMPAIGNS_SETTINGS_KEY}').get(campaign_id, {})


def to_user_info(user: User) -> UserInfo:
    return UserInfo(
        user_id=user.pk,
        level=user.user_type,
        mobile_number=user.mobile,
        webengage_id=user.get_webengage_id(),
    )


class BaseCampaign(ABC):
    id: str
    type: CampaignType

    def get_settings(self) -> Dict[str, Any]:
        return get_campaign_settings(self.id)

    def join(self, user_info: UserInfo, utm_params=None) -> UserCampaignInfo:
        pass

    def get_campaign_details(self, user_info: UserInfo) -> Dict[str, Any]:
        return {}

    def is_user_participated(self, user_info: UserInfo) -> Optional[bool]:
        return None


class RewardBasedCampaign(BaseCampaign):
    mission: BaseMission

    def check_reward_conditions(self, user_identifier: UserIdentifier, **kwargs):
        pass

    @abstractmethod
    def get_capacity_details(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def send_reward(self, user_identifier: UserIdentifier, **kwargs):
        raise NotImplementedError


class MobileVerificationBasedCampaign(BaseCampaign):

    def send_otp(self, user_identifier: UserIdentifier, utm_params=None):
        self.check_identifier(user_identifier)
        send_sms_otp(user_identifier.id, UserOTP.OTP_Usage.campaign)

    def verify_otp(
        self,
        user_identifier: UserIdentifier,
        verification_code: str,
        utm_params: UTMParameters,
    ) -> UserCampaignInfo:

        self.check_identifier(user_identifier)
        user, mobile_number = verify_sms_otp(user_identifier.id, verification_code, UserOTP.OTP_Usage.campaign)
        return UserCampaignInfo(user_details=self._to_user_info(user, mobile_number), campaign_details={})

    @staticmethod
    def check_identifier(user_identifier: UserIdentifier):
        if user_identifier.type != UserIdentifierType.MOBILE:
            raise InvalidUserIDException(
                f'identifier with type={user_identifier.type.value} is not supported for this campaign',
            )

    @staticmethod
    def _to_user_info(user, mobile_number):
        if user is None:
            return UserInfo(mobile_number=mobile_number, level=-1)

        return to_user_info(user)
