from decimal import Decimal

from django.db import transaction

from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from exchange.staking import errors
from exchange.staking.errors import run_safely_with_exception_report
from exchange.staking.helpers import OperationTime, StakingFeatureFlags
from exchange.staking.models import Plan, StakingTransaction, UserPlan, UserPlanRequest
from exchange.staking.models.helpers import add_to_transaction_amount
from exchange.staking.service.staking import get_staking_plan_to_end


@transaction.atomic
def add_and_apply_instant_end_request(
    user_id: int, plan_id: int, amount: Decimal, created_by_admin: bool = False
) -> StakingTransaction:
    instant_end_transaction = _create_instant_end_request(user_id=user_id, plan_id=plan_id, amount=amount)
    _apply_instant_end_request(user_id=user_id, plan_id=plan_id)

    add_user_plan_early_end_request(user_id=user_id, plan_id=plan_id, amount=amount, created_by_admin=created_by_admin)
    return instant_end_transaction


def _create_instant_end_request(user_id: int, plan_id: int, amount: Decimal) -> StakingTransaction:
    """When this method is being called, a transaction would be created to determine the amount to
    be reduced from staking and start un-staking process, in next operational time.
    """
    plan = Plan.get_plan_to_read(plan_id)
    if not plan.is_instantly_unstakable:
        raise errors.PlanIsNotInstantlyUnstakable('Creating instant end request for this plan is not possible.')
    if amount <= Decimal('0'):
        raise errors.InvalidAmount('Amount is too low.')

    StakingTransaction.get_lock(user_id, plan_id)

    # legacy code marked for removal
    try:
        staking = get_staking_plan_to_end(user_id, plan_id)
    except Plan.DoesNotExist as e:
        raise errors.InvalidPlanId('No staking on this planId.') from e

    if staking.staked_at + staking.staking_period <= ir_now():
        raise errors.CantEndReleasedStaking('Staking is already ended.')

    try:
        current_request = StakingTransaction.get_active_transaction_by_tp(
            user_id, plan_id, StakingTransaction.TYPES.instant_end_request
        )
    except StakingTransaction.DoesNotExist:
        current_request = None
    current_request_amount = current_request.amount if current_request else Decimal('0')
    new_staking_amount = plan.quantize_amount(staking.amount - current_request_amount - amount)
    new_request_amount = staking.amount - new_staking_amount
    return StakingTransaction.objects.create(
        user_id=user_id,
        plan_id=plan_id,
        parent=current_request,
        tp=StakingTransaction.TYPES.instant_end_request,
        amount=new_request_amount,
    )
    ###############################


def _apply_instant_end_request(user_id: int, plan_id: int) -> None:
    """When this method being called the requested amount would enter unstake period. Also staking
    amount and announced reward would change according to new staking amount.
    """
    # legacy code marked for removal
    StakingTransaction.get_lock(user_id, plan_id)
    try:
        user_request = StakingTransaction.get_active_transaction_by_tp(
            user_id, plan_id, StakingTransaction.TYPES.instant_end_request
        )
    except StakingTransaction.DoesNotExist:
        return
    unstake_amount = user_request.amount
    ###############################

    plan = Plan.get_plan_to_update(plan_id)
    plan.unblock_capacity(unstake_amount)

    # legacy code marked for removal
    staking_transaction = StakingTransaction.get_active_transaction_by_tp(
        user_id, plan_id, StakingTransaction.TYPES.stake
    )
    try:
        last_announced_reward = StakingTransaction.get_active_transaction_by_tp(
            user_id, plan_id, StakingTransaction.TYPES.announce_reward
        )
        delta_announced_reward_amount = -last_announced_reward.amount * unstake_amount / staking_transaction.amount
        add_to_transaction_amount(last_announced_reward, delta_announced_reward_amount)

    except StakingTransaction.DoesNotExist:
        pass

    add_to_transaction_amount(staking_transaction, -unstake_amount)
    StakingTransaction.objects.create(
        plan_id=plan_id,
        user_id=user_id,
        tp=StakingTransaction.TYPES.unstake,
        amount=unstake_amount,
        parent=user_request,
        created_at=OperationTime.get_next(),
    )
    ###############################


@run_safely_with_exception_report
def add_user_plan_early_end_request(
    user_id: int, plan_id: int, amount: Decimal, created_by_admin: bool = False
) -> None:
    if not Settings.get_flag(StakingFeatureFlags.API_DUAL_WRITE):
        return

    try:
        user_plan = UserPlan.objects.select_for_update(of=('self',)).get(
            user_id=user_id, plan_id=plan_id, status=UserPlan.Status.LOCKED
        )
    except UserPlan.DoesNotExist as e:
        raise errors.InvalidPlanId('No staking on this planId.') from e

    plan = Plan.get_plan_to_read(plan_id)
    new_staking_amount = plan.quantize_amount(user_plan.locked_amount - amount)
    new_request_amount = user_plan.locked_amount - new_staking_amount

    UserPlanRequest.objects.create(
        amount=new_request_amount,
        user_plan=user_plan,
        tp=UserPlanRequest.Type.EARLY_END,
        status=UserPlanRequest.Status.CREATED,
        created_by_admin=created_by_admin,
    )

    if user_plan.reward_amount > 0:
        reward_delta = user_plan.reward_amount * new_request_amount / user_plan.locked_amount
        user_plan.reward_amount -= reward_delta

    user_plan.locked_amount -= new_request_amount
    user_plan.early_ended_amount += new_request_amount

    update_fields = [
        'reward_amount',
        'locked_amount',
        'early_ended_amount',
    ]
    if user_plan.locked_amount == 0:
        user_plan.status = UserPlan.Status.RELEASED
        update_fields.append('status')

    user_plan.save(update_fields=update_fields)
