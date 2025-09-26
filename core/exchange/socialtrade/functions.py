from datetime import timedelta
from typing import Optional

from django.core.cache import cache
from django.db import models
from django.db.models import Count, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce, NullIf

from exchange.base.calendar import ir_now
from exchange.margin.models import Position
from exchange.socialtrade.constants import LEADER_WINRATE_CACHE_KEY
from exchange.socialtrade.enums import WinratePeriods
from exchange.socialtrade.models import Leader
from exchange.socialtrade.types import WinratesDict


def update_winrates(leader: Optional[Leader] = None) -> WinratesDict:
    """
    Calculate and update winrates for leaders and cache the results.

    Args:
        leader (Optional[Leader]): Optional leader instance to calculate winrate for.

    Returns:
        WinratesDict: A dictionary containing winrates for leaders
        with leader IDs as keys and dictionaries of winrates for different periods as values.
    """

    winrate_key = 'winrate_%s'

    # Create a subquery to calculate winrates for positions
    winrate_subquery = (
        Position.objects.filter(
            user_id=OuterRef('user_id'),
            status__in=[Position.STATUS.closed, Position.STATUS.liquidated],
        )
        .values('user_id')
        .annotate(
            winrate=Count('pk', filter=Q(pnl__gt=0)) * 100 / NullIf(Count('pk'), 0),
        )
        .distinct()
        .values('winrate')
    )

    # Calculate the winrate for positions
    winrates = Leader.objects.annotate(
        **{
            winrate_key
            % period.value: Coalesce(
                Subquery(
                    winrate_subquery.filter(closed_at__gte=ir_now() - timedelta(days=period.value)),
                    output_field=models.IntegerField(),
                ),
                0,
            )
            for period in WinratePeriods
        }
    ).values('pk', *(winrate_key % period.value for period in WinratePeriods))

    if leader:
        winrates = winrates.filter(pk=leader.pk)

    winrates_dict = {
        leader['pk']: {period.value: leader[winrate_key % period.value] for period in WinratePeriods}
        for leader in winrates
    }

    update_winrate_cache(winrates_dict)
    return winrates_dict


def update_winrate_cache(winrates: WinratesDict) -> None:
    """
    Update the cache with winrate data for leaders.

    Args:
        winrates (Winrates): A dictionary containing winrates for leaders
        with leader IDs as keys and dictionaries of winrates for different periods as values.
    """

    for leader_id, _winrates in winrates.items():
        for period, winrate in _winrates.items():
            cache_key = LEADER_WINRATE_CACHE_KEY % (leader_id, period)
            cache.set(cache_key, winrate)
