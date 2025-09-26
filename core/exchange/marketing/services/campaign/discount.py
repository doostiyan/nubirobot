from typing import Any, Dict

from exchange.marketing.services.campaign.base import CampaignType, RewardBasedCampaign, UserIdentifier
from exchange.promotions.discount import (
    calculate_dates_for_new_user_discount,
    check_active_user_discount,
    check_discount_has_enough_budget,
    check_discount_is_active,
    create_user_discount,
    get_discount_with_webengage_id,
)
from exchange.promotions.helper import get_user_id_with_webengage_cuid


class UserDiscountCampaign(RewardBasedCampaign):

    type = CampaignType.DISCOUNT

    def __init__(self, _id=None, mission=None):
        self.id = _id
        self.mission = mission

    def check_reward_conditions(self, user_identifier: UserIdentifier, **kwargs):
        user_id = get_user_id_with_webengage_cuid(user_identifier.id)
        discount = get_discount_with_webengage_id(kwargs['discount_id'])
        check_discount_is_active(discount)
        activation_date, end_date = calculate_dates_for_new_user_discount(discount)
        check_active_user_discount(user_id, activation_date, end_date)
        check_discount_has_enough_budget(discount)

    def send_reward(self, user_identifier: UserIdentifier, **kwargs):
        user_id = get_user_id_with_webengage_cuid(user_identifier.id)
        discount = get_discount_with_webengage_id(kwargs['discount_id'])
        check_discount_is_active(discount)
        create_user_discount(user_id, discount)

    def get_capacity_details(self) -> Dict[str, Any]:
        return {}
