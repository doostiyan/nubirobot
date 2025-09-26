import typing
import dataclasses
import datetime
import decimal


from django.core.cache import cache
from django.db import models

from exchange.staking.models import ExternalEarningPlatform, PlanTransaction, Plan


BEST_PERFORMING_PLANS_CACHE_KEY_TEMPLATE = 'best_performing_plans_{tp}'
BEST_PERFORMING_PLANS_CACHE_TTL = datetime.timedelta(hours=6)


@dataclasses.dataclass
class BestPerformingPlans:
    currency: int
    staking_period: datetime.timedelta
    realized_apr: decimal.Decimal


def _select_best_performing_plans(earn_type: int) -> typing.List[BestPerformingPlans]:
    active_plan_ids = Plan.filter_by_tp(Plan.all_active_plans(), earn_type).values_list('id', flat=True)
    ended_plans = Plan.objects.filter(
        external_platform__tp=earn_type,
        extended_to__in=active_plan_ids,
    )
    best_performing_plans = []
    currencies_with_best_performing_plans = set()
    for currency, staking_period, realized_apr in ended_plans.annotate(
        staking_period_days=models.functions.ExtractDay('staking_period'),
        realized_apr=models.ExpressionWrapper(
        models.Sum('transaction__amount', filter=(
            models.Q(transaction__tp=PlanTransaction.TYPES.announce_reward)
            & models.Q(transaction__child__tp=PlanTransaction.TYPES.give_reward)
        ),
        ) / models.F('total_capacity') / (
            models.Case(
                models.When(models.Q(staking_period_days=0), then=1),
                default=models.F('staking_period_days'),
            )
        ) * 365 * 100,
        output_field=models.DecimalField(),
        ),
    ).order_by('-realized_apr').values_list(
        'external_platform__currency',
        'staking_period',
        'realized_apr',
    ):
        if realized_apr is None:
            continue
        if currency in currencies_with_best_performing_plans:
            continue
        best_performing_plans.append(BestPerformingPlans(
            currency=currency,
            staking_period=staking_period,
            realized_apr=realized_apr,
        ))
        currencies_with_best_performing_plans.add(currency)

    return best_performing_plans[:4]


def _set_plans(tp: ExternalEarningPlatform.TYPES, plans: typing.List[BestPerformingPlans]) -> None:
    cache_key = BEST_PERFORMING_PLANS_CACHE_KEY_TEMPLATE.format(tp=tp)
    cache.set(cache_key, plans, BEST_PERFORMING_PLANS_CACHE_TTL.total_seconds())


def get_plans(tp: ExternalEarningPlatform.TYPES) -> typing.List[BestPerformingPlans]:
    cache_key = BEST_PERFORMING_PLANS_CACHE_KEY_TEMPLATE.format(tp=tp)
    plans = cache.get(cache_key)
    if plans is None:
        plans = _select_best_performing_plans(tp)
        _set_plans(tp, plans)
    return plans
