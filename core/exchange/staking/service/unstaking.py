from typing import Optional

from django.db.models import Q, QuerySet, Sum

from exchange.staking.models import StakingTransaction


def get_user_unstakings(user_id: int, plan_type: Optional[int] = None) -> QuerySet[StakingTransaction]:
    query = __get_unstaking_query().filter(user_id=user_id)
    if plan_type is not None:
        query = query.filter(plan__external_platform__tp=plan_type)
    query = query.order_by('id')
    return query


def __get_unstaking_query() -> QuerySet:
    return (
        StakingTransaction.objects.select_related('plan')
        .select_related('plan__external_platform')
        .filter(
            tp=StakingTransaction.TYPES.unstake,
        )
        .only(
            'id',
            'user_id',
            'created_at',
            'amount',
            'parent__tp',
            'plan_id',
            'plan__staked_at',
            'plan__staking_period',
            'plan__unstaking_period',
            'plan__external_platform__currency',
            'plan__external_platform__tp',
        )
        .annotate(
            released_amount=Sum(
                'child__amount',
                filter=Q(child__tp=StakingTransaction.TYPES.release),
            )
        )
    )
