from typing import Optional

from django.conf import settings

from exchange.accounts.models import User
from exchange.socialtrade.leaders.trades import LeaderTrades
from exchange.socialtrade.models import Leader, SocialTradeSubscription


def get_leaders_positions(
    user: User,
    leader_id: Optional[int] = None,
    side: Optional[int] = None,
    is_closed: Optional[bool] = None,
    *,
    include_closed=True,
):
    if leader_id is not None:
        single_leader = True
        leader = Leader.get_actives_for_user(user).get(id=leader_id)
        is_subscriber = leader.is_subscribed
        leaders = {leader.user_id: leader.id}

    else:
        single_leader = False
        leaders = {
            leader['leader__user_id']: leader['leader_id']
            for leader in SocialTradeSubscription.get_actives()
            .filter(subscriber=user)
            .values('leader_id', 'leader__user_id')
        }

    if not single_leader or is_subscriber:
        delay = settings.SOCIAL_TRADE['delayWhenSubscribed']
        duration = settings.SOCIAL_TRADE['durationWhenSubscribed']
    else:
        delay = settings.SOCIAL_TRADE['delayWhenUnsubscribed']
        duration = settings.SOCIAL_TRADE['durationWhenUnsubscribed']

    trade = LeaderTrades(leaders.keys(), delay, duration, side)
    return trade.get_positions(is_closed=is_closed, include_closed=include_closed).prefetch_related('orders'), leaders


def get_leaders_orders(user: User, leader_id: int, side: Optional[int] = None):
    leader = Leader.get_actives_for_user(user).get(id=leader_id)
    if leader.is_subscribed:
        delay = settings.SOCIAL_TRADE['delayWhenSubscribed']
        duration = settings.SOCIAL_TRADE['durationWhenSubscribed']
    else:
        delay = settings.SOCIAL_TRADE['delayWhenUnsubscribed']
        duration = settings.SOCIAL_TRADE['durationWhenUnsubscribed']

    return LeaderTrades([leader.user_id], delay, duration, side).get_orders()
