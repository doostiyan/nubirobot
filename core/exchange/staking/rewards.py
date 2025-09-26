from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from time import time
from typing import Optional

import pytz
from django.conf import settings
from django.db import transaction

from exchange.base.calendar import ir_now
from exchange.base.decorators import measure_time_cm
from exchange.base.models import Currencies
from exchange.blockchain.staking.base_staking import BaseStaking
from exchange.blockchain.staking.staking_factory import StakingFactory
from exchange.staking import errors
from exchange.staking.metrics import Metrics
from exchange.staking.models import ExternalEarningPlatform, Plan, PlanTransaction


@measure_time_cm(metric=str(Metrics.EXTERNAL_STAKE_FETCH_REWARD_TIME))
def _get_staking_reward_balance(
        network: str, address: str, currency: int, from_date: Optional[date], to_date: Optional[date],
) -> Decimal:
    if not settings.ENV == 'prod':
        return time()
    staking: BaseStaking = StakingFactory.get_staking(
        network=network, currency=currency, platform=None,
    )
    if staking is None:
        return None
    return  staking.get_staking_info(
        address, start_reward_period=from_date, end_reward_period=to_date,
    ).rewards_balance


def _fetch_periodic_staking_reward(plan: Plan,) -> None:
    nw = ir_now()
    try:
        last_fetched_reward_transaction = plan.get_active_transaction_by_tp(
            tp=PlanTransaction.TYPES.fetched_reward,
        )
        last_fetched_reward_date = last_fetched_reward_transaction.created_at.date()
    except PlanTransaction.DoesNotExist:
        last_fetched_reward_transaction = None
        last_fetched_reward_date = None

    # Check for recently fetched reward
    if last_fetched_reward_transaction and last_fetched_reward_transaction.created_at > nw - timedelta(hours=1):
        raise errors.TooSoon(
            f'Trying to fetch rewards for plan #{plan.id} '
            + 'while there is a recent fetched reward for this plan.'
        )

    # We should use UTC time zone to be consistent with block chain module
    fetch_reward_date = datetime.now(timezone.utc).date()

    if last_fetched_reward_date == fetch_reward_date:
        return

    last_reward_amount = last_fetched_reward_transaction.amount if last_fetched_reward_transaction else Decimal('0')

    # A day should be ended so we could fetch its rewards
    fetch_reward_date -= timedelta(days=1)

    # Since BNB block chain staking module accepts date (and not datetimes)
    # and since BNB Rewards will be assigned to external staking platform
    # at time 0:0:0 of UTC, And since PlanTransaction with type 'fetch_reward'
    # should present rewards till its created_at:
    if plan.currency != Currencies.bnb:
        fetch_reward_date += timedelta(days=1)

    staking_reward_balance = _get_staking_reward_balance(
        network=plan.external_platform.network,
        address=plan.external_platform.address,
        currency=plan.external_platform.currency,
        from_date=datetime.combine(fetch_reward_date, datetime.min.time(), pytz.UTC),
        to_date=datetime.combine(fetch_reward_date, datetime.max.time(), pytz.UTC),
    ) or 0
    PlanTransaction.objects.create(
        plan=plan,
        parent=last_fetched_reward_transaction,
        tp=PlanTransaction.TYPES.fetched_reward,
        amount=last_reward_amount + Decimal(str(staking_reward_balance,),),
        created_at=nw,
    )


def _fetch_non_periodic_staking_reward(plan: Plan,) -> None:

    try:
        last_fetched_reward_transaction = plan.get_active_transaction_by_tp(
            tp=PlanTransaction.TYPES.fetched_reward,
        )
    except PlanTransaction.DoesNotExist:
        last_fetched_reward_transaction = None

    nw = ir_now()
    # Check for recently fetched reward
    if last_fetched_reward_transaction and last_fetched_reward_transaction.created_at > nw - timedelta(hours=1):
        raise errors.TooSoon(
            f'Trying to fetch rewards for plan #{plan.id} '
            + 'while there is a recent fetched reward for this plan.'
        )

    staking_reward_balance = _get_staking_reward_balance(
        network=plan.external_platform.network,
        address=plan.external_platform.address,
        currency=plan.external_platform.currency,
        from_date=None,
        to_date=None,
    ) or 0
    PlanTransaction.objects.create(
        plan=plan,
        parent=last_fetched_reward_transaction,
        tp=PlanTransaction.TYPES.fetched_reward,
        amount=Decimal(str(staking_reward_balance),),
        created_at=nw,
    )


def _fetch_staking_reward(plan: Plan,) -> None:

    if plan.external_platform.currency in (Currencies.bnb,):
        return _fetch_periodic_staking_reward(plan,)

    if plan.external_platform.currency in (Currencies.ftm,):
        return _fetch_non_periodic_staking_reward(plan,)


def _fetch_yield_aggregator_reward(plan: Plan,) -> None:
    try:
        last_fetched_reward_transaction = plan.get_active_transaction_by_tp(
            tp=PlanTransaction.TYPES.fetched_reward,
        )
    except PlanTransaction.DoesNotExist:
        last_fetched_reward_transaction = None

    nw = ir_now()
    # Check for recently fetched reward
    if last_fetched_reward_transaction and last_fetched_reward_transaction.created_at > nw - timedelta(hours=1):
        raise errors.TooSoon(
            f'Trying to fetch rewards for plan #{plan.id} '
            + 'while there is a recent fetched reward for this plan.'
        )

    PlanTransaction.objects.create(
        plan=plan,
        parent=last_fetched_reward_transaction,
        tp=PlanTransaction.TYPES.fetched_reward,
        amount=Decimal('0'),
        created_at=nw,
    )


@transaction.atomic
def fetch_reward(plan_id: Plan,) -> None:
    plan = Plan.get_plan_to_update(plan_id,)

    if plan.external_platform.tp == ExternalEarningPlatform.TYPES.staking:
        return _fetch_staking_reward(plan)

    if plan.external_platform.tp == ExternalEarningPlatform.TYPES.yield_aggregator:
        return _fetch_yield_aggregator_reward(plan)

    raise NotImplementedError(
        'exchange.staking.fetch_reward module can not fetch reward for '
        + f'plan #{plan_id} with type \'{plan.external_platform.get_tp_display()}\'.'
        )
