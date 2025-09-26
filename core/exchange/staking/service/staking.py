from typing import Optional

from django.db.models import Exists, F, OuterRef, Q, QuerySet, Sum

from exchange.staking.models import Plan, StakingTransaction


def get_user_stakings(user_id: int, plan_type: Optional[int] = None) -> QuerySet['Plan']:
    query = __get_staking_query().filter(amount__gt=0, user_id=user_id).select_related('external_platform')
    if plan_type is not None:
        query = query.filter(external_platform__tp=plan_type)
    return query


def get_staking_plan_to_end(user_id: int, plan_id: int) -> 'Plan':
    plan = (
        Plan.objects.only(
            'id',
            'staked_at',
            'staking_period',
        )
        .annotate(
            extended_to_id=F('extended_to__id'),
            user_id=F('staking_transaction__user_id'),
            amount=Sum(
                'staking_transaction__amount',
                filter=Q(
                    staking_transaction__tp=StakingTransaction.TYPES.stake,
                ),
            ),
        )
        .get(amount__gt=0, id=plan_id, user_id=user_id)
    )
    return plan


def get_staking_extended_amount(user_id: int, plan_id: int):
    try:
        plan = (
            Plan.objects.only('id')
            .annotate(
                user_id=F('staking_transaction__user_id'),
                amount=Sum(
                    'staking_transaction__amount',
                    filter=Q(
                        staking_transaction__tp=StakingTransaction.TYPES.stake,
                    ),
                ),
                extended_amount=Sum(
                    'staking_transaction__amount',
                    filter=Q(
                        staking_transaction__tp=StakingTransaction.TYPES.extend_out,
                    ),
                ),
            )
            .get(user_id=user_id, id=plan_id, amount__gt=0)
        )
        return plan.extended_amount
    except Plan.DoesNotExist:
        return None


def __get_staking_query() -> QuerySet:
    return (
        Plan.objects.select_related('external_platform')
        .only(
            'id',
            'staked_at',
            'staking_period',
            'unstaking_period',
            'external_platform',
        )
        .annotate(
            extended_to_id=F('extended_to__id'),
            user_id=F('staking_transaction__user_id'),
            amount=Sum(
                'staking_transaction__amount',
                filter=Q(
                    staking_transaction__tp=StakingTransaction.TYPES.stake,
                ),
            ),
            announced_reward=Sum(
                'staking_transaction__amount',
                filter=Q(
                    staking_transaction__tp=StakingTransaction.TYPES.announce_reward,
                    staking_transaction__child=None,
                ),
            ),
            received_reward=Sum(
                'staking_transaction__amount',
                filter=Q(
                    staking_transaction__tp=StakingTransaction.TYPES.give_reward,
                ),
            ),
            released_amount=Sum(
                'staking_transaction__amount',
                filter=Q(
                    staking_transaction__tp=StakingTransaction.TYPES.release,
                ),
            ),
            extended_amount=Sum(
                'staking_transaction__amount',
                filter=Q(
                    staking_transaction__tp=StakingTransaction.TYPES.extend_out,
                ),
            ),
            instantly_unstaked_amount=Sum(
                'staking_transaction__amount',
                filter=Q(
                    staking_transaction__tp=StakingTransaction.TYPES.unstake,
                    staking_transaction__parent__tp=StakingTransaction.TYPES.instant_end_request,
                ),
            ),
            is_auto_extend_enabled=~Exists(
                StakingTransaction.objects.filter(
                    tp=StakingTransaction.TYPES.auto_end_request,
                    child=None,
                    plan_id=OuterRef('id'),
                    user_id=OuterRef('user_id'),
                ),
            ),
        )
    )
