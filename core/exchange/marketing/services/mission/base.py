from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict

from exchange.marketing.types import UserInfo


class CampaignMission(Enum):
    KYC_OR_REFER = 'kyc_or_refer'
    TRADE = 'trade'


class BaseMissionProgressStatus(Enum):
    NOT_STARTED = 'NOT_STARTED'
    DONE = 'DONE'

class BaseMission(ABC):
    validity_duration: int

    @classmethod
    @abstractmethod
    def initiate(cls, user_info: UserInfo, campaign_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def is_done(cls, user_info: UserInfo, campaign_id: str) -> bool:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def get_progress_details(cls, user_info: UserInfo, campaign_id: str) -> Dict[str, Any]:
        raise NotImplementedError
