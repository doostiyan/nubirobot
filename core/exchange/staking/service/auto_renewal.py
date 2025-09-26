from django.db import transaction

from exchange.base.models import Settings
from exchange.staking.errors import NonExtendablePlan, run_safely_with_exception_report
from exchange.staking.helpers import StakingFeatureFlags
from exchange.staking.models import Plan, StakingTransaction, UserPlan


def validate_can_auto_renew_plan(plan_id: int):
    plan = Plan.get_plan_to_read(plan_id)
    if not plan.is_extendable:
        raise NonExtendablePlan('Cant set auto-extend flag for un-extendable Plan.')


@transaction.atomic
def set_plan_auto_renewal(plan_id: int, user_id: int, allow_renewal: bool = False):
    plan = Plan.get_plan_to_read(plan_id)
    if plan.is_extendable is False or allow_renewal is None:
        return

    _set_staking_transactions_auto_renewal(plan_id=plan_id, user_id=user_id, allow_renewal=allow_renewal)
    _set_user_plan_auto_renewal(plan_id=plan_id, user_id=user_id, allow_renewal=allow_renewal)


def _set_staking_transactions_auto_renewal(plan_id: int, user_id: int, allow_renewal: bool):
    if allow_renewal is False:
        StakingTransaction.enable_auto_end(user_id, plan_id)
    elif allow_renewal is True:
        StakingTransaction.disable_auto_end(user_id, plan_id)


@run_safely_with_exception_report
def _set_user_plan_auto_renewal(plan_id: int, user_id: int, allow_renewal: bool):
    if not Settings.get_flag(StakingFeatureFlags.API_DUAL_WRITE):
        return

    UserPlan.objects.filter(
            user_id=user_id,
            plan_id=plan_id,
            status__in=UserPlan.ALLOW_CHANGE_AUTO_RENEWAL_STATUS,
        ).update(auto_renewal=allow_renewal)
