"""Method defined here will be used in other Apps"""
import decimal
import functools
from typing import Dict

from django.db import models

from exchange.staking.models import StakingTransaction, ExternalEarningPlatform


# These method make query and returns staking and yeld farming blocked balances,
# In some cases (for example `/earn/balances`) both of `get_balances_blocked_in_staking`
# and `get_balances_blocked_in_yield_aggregator` would be called, hence we are caching
# these function to prevent instantly making the same query. (Note that bigger cache sizes
# might lead to un-updated return value these function for some time).
@functools.lru_cache(maxsize=1)
def _get_blocked_balances(user_id: int) -> Dict[int, Dict[int, decimal.Decimal]]:
    balances = StakingTransaction.objects.filter(user_id=user_id).values(
        'plan__external_platform__currency', 'plan__external_platform__tp',
    ).annotate(
        blocked_balance=models.Sum('amount', filter=models.Q(
            tp=StakingTransaction.TYPES.create_request
        ) & ~models.Q(
            child__tp=StakingTransaction.TYPES.create_request
        )),
        released_balance=models.Sum('amount', filter=models.Q(tp__in=(
            StakingTransaction.TYPES.cancel_create_request,
            StakingTransaction.TYPES.system_rejected_create,
            StakingTransaction.TYPES.admin_rejected_create,
            StakingTransaction.TYPES.release,
        ),),)
    ).values_list(
        'plan__external_platform__currency', 'plan__external_platform__tp', 'blocked_balance', 'released_balance',
    )
    nobifi_balances = {}
    for tp in ExternalEarningPlatform.TYPES._db_values:
        nobifi_balances[tp] = {}
        for currency, _tp, blocked_balance, released_balance in balances:
            if not _tp == tp:
                continue
            value = (blocked_balance or decimal.Decimal('0')) - (released_balance or decimal.Decimal('0'))
            if not value:
                continue
            nobifi_balances[tp][currency] = value
    return nobifi_balances


def get_balances_blocked_in_staking(user_id: int) -> Dict[int, decimal.Decimal]:
    return _get_blocked_balances(user_id,).get(ExternalEarningPlatform.TYPES.staking,) or {}


def get_balances_blocked_in_yield_aggregator(user_id: int) -> Dict[int, decimal.Decimal]:
    return _get_blocked_balances(user_id,).get(ExternalEarningPlatform.TYPES.yield_aggregator) or {}
