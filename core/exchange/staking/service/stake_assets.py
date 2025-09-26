from decimal import Decimal

from django.db import transaction

from exchange.base.calendar import ir_now
from exchange.base.logging import report_event, report_exception
from exchange.base.models import Settings
from exchange.staking import errors
from exchange.staking.admin_notifier import notify_or_raise_exception_decorator
from exchange.staking.errors import run_safely_with_exception_report
from exchange.staking.helpers import StakingFeatureFlags
from exchange.staking.models import Plan, PlanTransaction, StakingTransaction, UserPlan, UserPlanRequest


def stake_all_users_assets(plan_id: int):
    _create_stake_assets_transactions(plan_id)
    lock_user_plans(plan_id)
    check_plan_over_staking(plan_id)


def _create_stake_assets_transactions(plan_id: int) -> None:
    for user_id in Plan.get_plan_user_ids(plan_id):
        try:
            notify_or_raise_exception_decorator(stake_user_assets)(user_id, plan_id)
        except Exception:
            report_exception()


@transaction.atomic
def stake_user_assets(user_id: int, plan_id: int) -> None:
    StakingTransaction.get_lock(user_id, plan_id)
    try:
        request = StakingTransaction.get_active_transaction_by_tp(
            user_id, plan_id, StakingTransaction.TYPES.create_request
        )
    except StakingTransaction.DoesNotExist as e:
        if StakingTransaction.does_transaction_exists(user_id, plan_id, [StakingTransaction.TYPES.stake]):
            raise errors.AssetAlreadyStaked('Assets been already staked.') from e
        if StakingTransaction.does_transaction_exists(
            user_id, plan_id, [StakingTransaction.TYPES.system_rejected_create]
        ):
            raise errors.SystemRejectedCreateRequest('User create request been rejected by system.') from e
        raise errors.ParentIsNotCreated('There is no Staking request.') from e

    plan = Plan.get_plan_to_update(plan_id)
    try:
        plan_stake_transaction = plan.get_active_transaction_by_tp(PlanTransaction.TYPES.stake)
    except PlanTransaction.DoesNotExist as e:
        raise errors.PlanTransactionIsNotCreated('Plan assets has not been staked yet.') from e

    StakingTransaction.add_to_stake_amount(user_id, plan_id, request.amount)
    plan.add_to_stake_amount(-request.amount)
    StakingTransaction.objects.create(
        user_id=user_id,
        plan_id=plan_id,
        tp=StakingTransaction.TYPES.system_accepted_create,
        amount=request.amount,
        parent=request,
        created_at=plan_stake_transaction.created_at,
        plan_transaction=plan_stake_transaction,
    )


@run_safely_with_exception_report
@transaction.atomic
def lock_user_plans(plan_id: int):
    # StakingTransaction.get_lock(user_id, plan_id) todo
    if not Settings.get_flag(StakingFeatureFlags.CRONJOB_DUAL_WRITE):
        return

    plan = Plan.get_plan_to_update(plan_id)
    try:
        plan.get_active_transaction_by_tp(PlanTransaction.TYPES.stake)
    except PlanTransaction.DoesNotExist as e:
        raise errors.PlanTransactionIsNotCreated('Plan assets has not been staked yet.') from e

    UserPlan.objects.filter(
        plan_id=plan_id,
        status__in=[UserPlan.Status.REQUESTED, UserPlan.Status.EXTEND_FROM_PREVIOUS_CYCLE],
        locked_amount__gt=0,
    ).update(status=UserPlan.Status.LOCKED, locked_at=ir_now())

    UserPlanRequest.objects.filter(
        user_plan__plan_id=plan_id,
        tp=UserPlanRequest.Type.SUBSCRIPTION,
        status=UserPlanRequest.Status.CREATED,
    ).update(status=UserPlanRequest.Status.ACCEPTED)


def check_plan_over_staking(plan_id: int):
    plan = Plan.get_plan_to_read(plan_id)
    try:
        plan_stake_transaction = plan.get_active_transaction_by_tp(PlanTransaction.TYPES.stake)
    except PlanTransaction.DoesNotExist as e:
        return

    if plan_stake_transaction.amount < Decimal('0'):
        report_event(
            message='UnexpectedError.OverStaking',
            level='error',
            tags={'module': 'staking'},
            extras={'plan_id': plan_id, 'amount': plan_stake_transaction.amount},
        )
