import json
from typing import Any, Dict

from django.db.models import Case, Count, IntegerField, Q, Sum, Value, When

from exchange.accounts.models import User, UserReferral
from exchange.base.calendar import get_earliest_time, get_latest_time, parse_shamsi_date
from exchange.base.models import Settings
from exchange.base.parsers import parse_int
from exchange.marketing.exceptions import InvalidUserIDException
from exchange.marketing.services.campaign.base import BaseCampaign
from exchange.marketing.types import UserInfo


class ReferralCampaign(BaseCampaign):

    def get_campaign_details(self, user_info: UserInfo) -> Dict[str, Any]:
        if user_info.user_id is None:
            raise InvalidUserIDException()

        shamsi_start_date = Settings.get_value('referral_campaign_start_date')
        shamsi_end_date = Settings.get_value('referral_campaign_end_date')
        start_date = get_earliest_time(parse_shamsi_date(shamsi_start_date.strip()))
        end_date = get_latest_time(parse_shamsi_date(shamsi_end_date.strip()))
        date_bonus_settings = Settings.get('referral_campaign_special_dates') or None
        if not date_bonus_settings:
            date_bonus_settings = dict()
        else:
            date_bonus_settings = {
                parse_shamsi_date(k): parse_int(v or 0) for k, v in json.loads(date_bonus_settings).items()
            }
        when_conditions = [When(child__user_type__lt=User.USER_TYPES.level1, then=Value(0))] + [
            When(created_at__date=date, then=Value(ratio if 1 <= ratio <= 3 else 1))
            for date, ratio in date_bonus_settings.items()
        ]

        user_referrals = UserReferral.objects.filter(
            parent_id=user_info.user_id,
            created_at__gte=start_date,
            created_at__lte=end_date,
        ).aggregate(
            users_referred_count=Count('pk'),
            authorized_user_referrals=Count('pk', filter=Q(child__user_type__gte=User.USER_TYPES.level1)),
            total_bonus=Sum(
                Case(*when_conditions, default=Value(1), output_field=IntegerField()), output_field=IntegerField()
            ),
        )
        return user_referrals
