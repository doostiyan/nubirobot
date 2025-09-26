import datetime
from typing import Optional

from django.db.models import Case, Count, DecimalField, F, Max, Min, Sum, When
from django.db.models.query_utils import Q
from django.utils.timezone import now

from exchange.base.logging import report_exception
from exchange.base.models import Settings
from exchange.web_engage.externals.web_engage import call_on_webengage_active, web_engage_user_api
from exchange.web_engage.types import UserData, UserOrderSummary, UserReferralData
from exchange.web_engage.utils import get_toman_amount_display, is_webengage_user


@call_on_webengage_active
def send_user_data_to_webengage(user) -> None:
    from exchange.web_engage.tasks import task_send_user_data_to_web_engage

    if not is_webengage_user(user):
        return
    if "all_user_data" in Settings.get_list("webengage_stopped_events"):
        return

    task_send_user_data_to_web_engage.delay(user.id)


def send_user_base_data(user_id: int) -> None:
    user_data = _get_user_base_data(user_id=user_id)
    web_engage_user_api.send_base_info(user_data)


def _get_user_base_data(user_id: int) -> UserData:
    from exchange.accounts.models import User
    from exchange.market.models import Market, OrderMatching

    user = User.objects.get(id=user_id)
    user_orders = OrderMatching.get_trades(user=user_id).aggregate(
        total=Sum(
            Case(
                When(market__in=Market.get_rial_market_ids(), then=F('matched_price') * F('matched_amount')),
                When(market__in=Market.get_tether_market_ids(), then=F('matched_price') * F('matched_amount') * 300000),
            ),
            output_field=DecimalField(),
            default=0,
        ),
        count=Count('*'),
        last=Max('created_at'),
        first=Min('created_at'),
    )
    order_summary = UserOrderSummary(
        last_order_date=user_orders['last'].strftime("%Y-%m-%dT%H:%M:%S%z") if user_orders['last'] else None,
        first_order_date=user_orders['first'].strftime("%Y-%m-%dT%H:%M:%S%z") if user_orders['first'] else None,
        total_order_value_code=get_toman_amount_display((user_orders['total'] or 0) // 10),
        total_orders=user_orders['count'],
    )
    return UserData(user, order_summary, _get_active_user_campaign(user))


def _get_active_user_campaign(user) -> Optional[str]:
    from exchange.marketing.services.campaign.selector import get_active_campaigns
    from exchange.marketing.services.campaign.base import to_user_info

    try:
        active_campaigns = get_active_campaigns()
        participated_campaigns = filter(
            lambda campaign: campaign.is_user_participated(to_user_info(user)) == True, active_campaigns
        )
        return next(map(lambda c: c.id, participated_campaigns), None)
    except:
        report_exception()
        return None


def send_user_referral_data(user_id: int) -> None:
    referral_data = _get_user_referral_data(user_id=user_id)
    web_engage_user_api.send_referral_info(referral_data)


def send_user_campaign_data(webenge_user_id: str, campaign_id: str) -> None:
    web_engage_user_api.send_user_campaign_info(webenge_user_id, campaign_id)


def _get_user_referral_data(user_id: int):
    from exchange.accounts.models import User, UserReferral

    user_referrals = UserReferral.objects.filter(parent_id=user_id).aggregate(
        users_referred_count=Count('pk'),
        authorized_user_referrals=Count('pk', filter=Q(child__user_type__gte=User.USER_TYPES.level1)),
    )

    return UserReferralData(
        web_engage_user_id=User.objects.get(pk=user_id).get_webengage_id(),
        referred_count=user_referrals.get('users_referred_count') or 0,
        authorized_count=user_referrals.get('authorized_user_referrals') or 0,
    )


def get_users_have_trade_last_day():
    from exchange.market.models import OrderMatching

    trades = OrderMatching.objects.filter(
        created_at__lte=now(),
        created_at__gt=now() - datetime.timedelta(hours=24.1),
    )
    return set(trades.values_list('buyer_id', flat=True).distinct()).union(
        set(trades.values_list('seller_id', flat=True).distinct())
    )
