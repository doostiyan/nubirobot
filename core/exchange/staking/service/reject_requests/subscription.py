from decimal import Decimal

from django.db import transaction

from exchange.staking import errors
from exchange.staking.models import ExternalEarningPlatform, Plan, StakingTransaction
from exchange.wallet.helpers import RefMod, create_and_commit_transaction


@transaction.atomic
def reject_user_subscription(user_id: int, plan_id: int, amount: Decimal) -> StakingTransaction:
    reject_transaction = _create_reject_transaction(user_id, plan_id, amount)

    return reject_transaction


def _create_reject_transaction(user_id: int, plan_id: int, amount: Decimal) -> 'StakingTransaction':
    StakingTransaction.get_lock(user_id, plan_id)

    plan = Plan.get_plan_to_update(plan_id)
    amount = plan.quantize_amount(amount=amount)
    plan.unblock_capacity(amount)

    try:
        current_request = StakingTransaction.get_active_transaction_by_tp(
            user_id, plan_id, StakingTransaction.TYPES.create_request
        )
    except StakingTransaction.DoesNotExist:
        current_request = None
    current_amount = Decimal('0') if current_request is None else current_request.amount

    new_amount = plan.quantize_amount(amount=current_amount - amount)

    reject_request = StakingTransaction.objects.create(
        user_id=user_id,
        plan_id=plan_id,
        parent=current_request,
        tp=StakingTransaction.TYPES.admin_rejected_create,
        amount=amount,
    )
    try:
        wallet_transaction = create_and_commit_transaction(
            user_id=user_id,
            currency=plan.currency,
            amount=amount,
            ref_id=reject_request.id,
            ref_module={
                ExternalEarningPlatform.TYPES.staking: RefMod.staking_request,
                ExternalEarningPlatform.TYPES.yield_aggregator: RefMod.yield_farming_request,
            }.get(plan.external_platform.tp),
            description=f'لغو درخواست مشارکت در {plan.fa_description}',
        )
    except ValueError as e:
        raise errors.FailedAssetTransfer(f'User cannot cancel they staking request on plan #{plan_id}') from e

    reject_request.wallet_transaction = wallet_transaction
    reject_request.save(update_fields=('wallet_transaction',))

    if new_amount > 0:
        StakingTransaction.objects.create(
            user_id=user_id,
            plan_id=plan_id,
            parent=current_request,
            tp=StakingTransaction.TYPES.create_request,
            amount=new_amount,
        )
    return reject_request
