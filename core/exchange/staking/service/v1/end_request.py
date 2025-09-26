from decimal import Decimal

from django.db import transaction

from exchange.base.calendar import ir_now
from exchange.staking import errors
from exchange.staking.models import Plan, StakingTransaction


@transaction.atomic
def create_end_request(user_id: int, plan_id: int, amount: Decimal) -> StakingTransaction:
    return _create_end_request_transaction(user_id=user_id, plan_id=plan_id, amount=amount)


def _create_end_request_transaction(user_id: int, plan_id: int, amount: Decimal) -> StakingTransaction:
    if amount <= Decimal('0'):
        raise errors.InvalidAmount('Amount should be positive.')
    StakingTransaction.get_lock(user_id, plan_id)
    plan = Plan.get_plan_to_read(plan_id)
    if not plan.is_extendable:
        raise errors.NonExtendablePlan('Plan is not extendable.')

    try:
        staking = StakingTransaction.get_active_transaction_by_tp(user_id, plan_id, tp=StakingTransaction.TYPES.stake)
    except StakingTransaction.DoesNotExist as e:
        raise errors.ParentIsNotCreated('There is no staking to end.') from e

    try:
        current_amount = StakingTransaction.get_active_transaction_by_tp(
            user_id, plan_id, StakingTransaction.TYPES.end_request
        ).amount
    except StakingTransaction.DoesNotExist:
        current_amount = Decimal('0')

    try:
        new_stake_amount = plan.quantize_amount(staking.amount - (current_amount + amount))
    except errors.InvalidAmount as e:
        if current_amount == Decimal('0'):
            raise
        raise errors.RequestAccumulationInvalidAmount(e.message) from e
    new_end_request_amount = staking.amount - new_stake_amount

    request, _ = StakingTransaction.objects.update_or_create(
        user_id=user_id,
        plan_id=plan_id,
        tp=StakingTransaction.TYPES.end_request,
        defaults=dict(
            amount=new_end_request_amount,
            created_at=ir_now(),
        ),
    )
    return request
