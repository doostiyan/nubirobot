import datetime
from decimal import Decimal
from typing import Optional

from exchange.base.calendar import ir_now
from exchange.base.models import get_currency_codename
from exchange.base.serializers import register_serializer, serialize_decimal
from exchange.staking.best_performing_plans import BestPerformingPlans
from exchange.staking.models import ExternalEarningPlatform, Plan, StakingTransaction


def serialize_user_unsubscriptions(
    unstaking: StakingTransaction,
):
    return {
        'id': unstaking.id,
        'createdAt': unstaking.created_at.isoformat(),
        'releaseAt': (
            unstaking.created_at
            + (
                datetime.timedelta(0)
                if unstaking.parent is not None and unstaking.parent.tp == StakingTransaction.TYPES.instant_end_request
                else unstaking.plan.unstaking_period
            )
        ).isoformat(),
        'amount': serialize_decimal(unstaking.amount),
        'releasedAmount': serialize_decimal(unstaking.released_amount or Decimal(0)),
        'type': next(
            name
            for name, value in StakingTransaction.TYPES._identifier_map.items()  # pylint: disable=protected-access
            if value == unstaking.parent.tp
        ) if unstaking.parent is not None else 'non_extendable_plan',
        'planId': unstaking.plan_id,
        'planStartedAt': unstaking.plan.staked_at.isoformat(),
        'planStakingPeriod': unstaking.plan.staking_period.total_seconds(),
        'planCurrency': get_currency_codename(unstaking.plan.external_platform.currency),
        'planType': ExternalEarningPlatform.get_type_machine_display(unstaking.plan.external_platform.tp),
    }


@register_serializer(model=StakingTransaction)
def serialize_staking_transaction(
    staking_transaction: StakingTransaction, opts: Optional[dict] = None,  # pylint: disable=unused-argument
):
    tp = {
        StakingTransaction.TYPES.create_request: 'create',
        StakingTransaction.TYPES.cancel_create_request: 'cancel_create',
        StakingTransaction.TYPES.end_request: 'end',
        StakingTransaction.TYPES.cancel_end_request: 'cancel_end',
        StakingTransaction.TYPES.instant_end_request: 'instant_end',
    }.get(staking_transaction.tp) or next(
        name for name, value in StakingTransaction.TYPES._identifier_map.items(  # pylint: disable=protected-access
        ) if value == staking_transaction.tp
    )
    data = {
        'id': staking_transaction.id,
        'planId': staking_transaction.plan_id,
        'type': tp,
        'amount': staking_transaction.amount,
        'createdAt': staking_transaction.created_at,
    }
    if opts.get('level', 1) == 2:
        data['plan'] = staking_transaction.plan
    return data


def serialize_v1_end_request(staking_transaction: StakingTransaction):
    return {
        'id': staking_transaction.id,
        'planId': staking_transaction.plan_id,
        'type': 'end',
        'amount': staking_transaction.amount,
        'createdAt': staking_transaction.created_at,
    }


def serialize_user_subscriptions(staking: Plan):
    started_at = staking.staked_at
    ended_at = started_at + staking.staking_period
    released_at = ended_at + staking.unstaking_period
    status = 'released' if ir_now() > released_at else 'unstaked' if ir_now() > ended_at else 'staked'
    tp = ExternalEarningPlatform.get_type_machine_display(tp=staking.external_platform.tp)

    return {
        'planId': staking.id,
        'currency': get_currency_codename(staking.external_platform.currency),
        'status': status,
        'type': tp,
        'startedAt': started_at.isoformat(),
        'endedAt': ended_at.isoformat(),
        'releasedAt': released_at.isoformat(),
        'amount': serialize_decimal(staking.amount or Decimal('0')),
        'releasedAmount': serialize_decimal(staking.released_amount or Decimal('0')),
        'receivedReward': serialize_decimal(staking.received_reward or Decimal('0')),
        'announcedReward': serialize_decimal(staking.announced_reward or Decimal('0')),
        'extendedAmount': serialize_decimal(staking.extended_amount or Decimal('0')),
        'instantlyUnstakedAmount': serialize_decimal(staking.instantly_unstaked_amount or Decimal('0')),
        'extendedPlanId': staking.extended_to_id,
        'isPlanExtendable': staking.is_extendable,
        'stakingPrecision': serialize_decimal(staking.staking_precision),
        'isAutoExtendEnabled': staking.is_extendable and staking.is_auto_extend_enabled,
        'isInstantlyUnstakable': staking.is_instantly_unstakable,
    }


@register_serializer(model=Plan)
def serialize_plan(
    plan: Plan, opts: Optional[dict] = None,  # pylint: disable=unused-argument
):
    tp = ExternalEarningPlatform.get_type_machine_display(tp=plan.external_platform.tp)
    if plan.total_capacity - plan.filled_capacity < plan.min_staking_amount:
        plan.filled_capacity = plan.total_capacity

    status = ('close' if ir_now() < plan.opened_at or ir_now() > plan.opened_at + plan.request_period else (
            'full' if plan.total_capacity - plan.filled_capacity < plan.min_staking_amount else 'open'
    ))

    return {
        'id': plan.id,
        'type': tp,
        'currency': get_currency_codename(plan.external_platform.currency),
        'totalCapacity': plan.total_capacity,
        'filledCapacity': plan.filled_capacity,
        'estimatedAPR': Decimal('100') * plan.estimated_annual_rate,
        'minStakingAmount': plan.min_staking_amount,
        'stakingPrecision': plan.staking_precision,
        'isExtendable': plan.is_extendable,
        'rewardAnnouncementPeriod': plan.reward_announcement_period.total_seconds(),
        'openedAt': plan.opened_at,
        'requestPeriod': plan.request_period.total_seconds(),
        'stakedAt': plan.staked_at,
        'stakingPeriod': plan.staking_period.total_seconds(),
        'unstakePeriod': plan.unstaking_period.total_seconds(),
        'status': status,
        'isInstantlyUnstakable': plan.is_instantly_unstakable,
    }


@register_serializer(model=BestPerformingPlans)
def serialize_best_performin_plan(
    plan: BestPerformingPlans, opts: Optional[dict] = None,  # pylint: disable=unused-argument
):
    return {
        'currency': get_currency_codename(plan.currency),
        'stakingPeriod': plan.staking_period.total_seconds(),
        'realizedAPR': plan.realized_apr.quantize(Decimal('.00')),
    }
