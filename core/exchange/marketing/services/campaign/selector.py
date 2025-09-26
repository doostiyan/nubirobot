from functools import lru_cache
from typing import List

from exchange.base.models import Settings
from exchange.marketing.exceptions import InvalidCampaignException
from exchange.marketing.services.campaign.base import BaseCampaign, CampaignType
from exchange.marketing.services.campaign.discount import UserDiscountCampaign
from exchange.marketing.services.campaign.external_discount import ExternalDiscountCampaign
from exchange.marketing.services.campaign.referral import ReferralCampaign
from exchange.marketing.services.mission.base import CampaignMission
from exchange.marketing.services.mission.kyc_or_refer import KycOrReferMission
from exchange.marketing.services.mission.trade import TradeMission

campaign_types = [CampaignType.REFERRAL, CampaignType.DISCOUNT, CampaignType.EXTERNAL_DISCOUNT]
campaign_missions = [CampaignMission.KYC_OR_REFER]

ACTIVE_CAMPAIGNS_SETTINGS_KEY = 'active_campaigns'


def get_active_campaigns() -> List[BaseCampaign]:
    return list(map(_get_campaign_by_name, Settings.get_list(ACTIVE_CAMPAIGNS_SETTINGS_KEY)))


def choose_campaign_by_name(name):
    """
    sample campaign name : external_discount:kyc_or_refer:10M_Nobitex_Snapp
    """
    active_campaigns = Settings.get_list(ACTIVE_CAMPAIGNS_SETTINGS_KEY)
    if name not in active_campaigns:
        raise InvalidCampaignException(f'not found any active campaign for name={name}')
    return _get_campaign_by_name(name)


def _get_campaign_by_name(name) -> BaseCampaign:
    result = name.split(':')
    if len(result) != 3:
        raise InvalidCampaignException()

    campaign_type, campaign_mission, campaign_id = result

    type = next((t for t in CampaignType if t.value == campaign_type), None)
    mission = next((m for m in CampaignMission if m.value == campaign_mission), None)

    if not type:
        raise InvalidCampaignException(f'not found any campaign for type={campaign_type}, mission={campaign_mission}')

    return choose_campaign_by_type(type, mission, campaign_id)


@lru_cache
def choose_campaign_by_type(
    campaign_type: CampaignType,
    mission_type: CampaignMission = None,
    _id=None,
) -> BaseCampaign:
    mission = None
    if mission_type == CampaignMission.KYC_OR_REFER:
        mission = KycOrReferMission()
    elif mission_type == CampaignMission.TRADE:
        mission = TradeMission()

    if campaign_type == CampaignType.REFERRAL:
        return ReferralCampaign()
    if campaign_type == CampaignType.DISCOUNT:
        return UserDiscountCampaign(_id, mission)
    if campaign_type == CampaignType.EXTERNAL_DISCOUNT:
        return ExternalDiscountCampaign(_id, mission)

    raise InvalidCampaignException(f'not found any campaign for type={campaign_type}')


def check_campaign_type(instance: BaseCampaign, _type):
    if not isinstance(instance, _type):
        raise InvalidCampaignException('campaign type is invalid for this request.')
