from decimal import Decimal

from django.db import transaction
from django.db.models import F

from exchange.base.calendar import ir_now
from exchange.base.logging import report_exception
from exchange.base.models import Settings
from exchange.staking import errors
from exchange.staking.admin_notifier import notify_or_raise_exception_decorator
from exchange.staking.errors import InvalidPlanId, run_safely_with_exception_report
from exchange.staking.helpers import StakingFeatureFlags, is_v1_end_request_active
from exchange.staking.models import Plan, StakingTransaction, UserPlan, UserPlanRequest


def end_all_users_staking(plan_id: int):
    _create_end_staking_transactions(plan_id)
    _end_user_plans(plan_id)


def _create_end_staking_transactions(plan_id: int):
    for user_id in Plan.get_plan_user_ids_of_users_with_staked_assets(
        plan_id,
    ):
        try:
            notify_or_raise_exception_decorator(end_user_staking)(user_id, plan_id)
        except Exception:
            report_exception()


@transaction.atomic
def end_user_staking(user_id: int, plan_id: int) -> None:
    """In this Method after ending of staking period, according to active auto_end_request
    transaction, or if staking v1 end request has not been deactivated, extend_out and
    (if applicable) unstake transactions would be created.
    """
    plan = Plan.get_plan_to_read(plan_id)
    if ir_now() < plan.staked_at + plan.staking_period:
        raise errors.TooSoon('Too soon to end staking.')

    StakingTransaction.get_lock(user_id, plan_id)
    try:
        staking_transaction = StakingTransaction.get_active_transaction_by_tp(
            user_id, plan_id, StakingTransaction.TYPES.stake
        )
    except StakingTransaction.DoesNotExist as e:
        if StakingTransaction.does_transaction_exists(user_id, plan_id, (StakingTransaction.TYPES.extend_out,)):
            raise errors.AlreadyCreated('Staking has been already ended.') from e
        # Here, we can infer that there wasn't a staking for this user in this plan
        raise errors.ParentIsNotCreated('No staking to end.') from e

    if not plan.is_extendable:
        end_request_transaction = None
        end_request_amount = staking_transaction.amount

    else:  # `plan.is_extendable` is `True`

        def get_end_request_and_amount():
            try:
                end_request_transaction = StakingTransaction.get_active_transaction_by_tp(
                    user_id,
                    plan_id,
                    StakingTransaction.TYPES.auto_end_request,
                )
            except StakingTransaction.DoesNotExist:
                pass
            else:
                return end_request_transaction, staking_transaction.amount

            try:
                end_request_transaction = StakingTransaction.get_active_transaction_by_tp(
                    user_id,
                    plan_id,
                    StakingTransaction.TYPES.instant_end_request,
                )
            except StakingTransaction.DoesNotExist:
                pass
            else:
                return end_request_transaction, end_request_transaction.amount

            if not is_v1_end_request_active():
                return None, Decimal('0')

            try:
                end_request_transaction = StakingTransaction.get_active_transaction_by_tp(
                    user_id,
                    plan_id,
                    StakingTransaction.TYPES.end_request,
                )

            except StakingTransaction.DoesNotExist:
                return None, Decimal('0')
            else:
                return end_request_transaction, end_request_transaction.amount

        end_request_transaction, end_request_amount = get_end_request_and_amount()

    # Dont let user to unstake more than their staking.
    if end_request_amount > staking_transaction.amount:
        end_request_amount = staking_transaction.amount

    # Dont let user to extend more than their staking.
    if end_request_amount < Decimal('0'):
        end_request_amount = Decimal('0')

    # Deactivate `end_request` transaction
    if end_request_transaction is not None:
        StakingTransaction.objects.create(
            user_id=user_id,
            plan_id=plan_id,
            tp=StakingTransaction.TYPES.system_accepted_end,
            amount=end_request_amount,
            parent=end_request_transaction,
        )

    # Creating `unstake` transaction
    amount_to_unstake = end_request_amount
    if amount_to_unstake:
        StakingTransaction.objects.create(
            user_id=user_id,
            plan_id=plan_id,
            tp=StakingTransaction.TYPES.unstake,
            amount=amount_to_unstake,
            parent=end_request_transaction,
        )

    # Creating `stake_out` transaction
    amount_to_extend = staking_transaction.amount - amount_to_unstake
    StakingTransaction.objects.create(
        user_id=user_id,
        plan_id=plan_id,
        tp=StakingTransaction.TYPES.extend_out,
        amount=amount_to_extend,
        parent=staking_transaction,
    )


@run_safely_with_exception_report
@transaction.atomic
def _end_user_plans(plan_id: int) -> None:
    if not Settings.get_flag(StakingFeatureFlags.CRONJOB_DUAL_WRITE):
        return

    # StakingTransaction.get_lock(user_id, plan_id)  # todo , or keep lock plan
    plan = Plan.get_plan_to_update(plan_id)
    if ir_now() < plan.staked_at + plan.staking_period:
        raise errors.TooSoon('Too soon to end staking.')

    if not plan.is_extendable:
        UserPlan.objects.filter(
            plan_id=plan_id,
            status=UserPlan.Status.LOCKED,
            locked_amount__gt=0,
        ).update(status=UserPlan.Status.PENDING_RELEASE, unlocked_at=ir_now())

        return

    # update users that do not wanna renew
    UserPlan.objects.filter(
        plan_id=plan_id,
        status=UserPlan.Status.LOCKED,
        auto_renewal=False,
        locked_amount__gt=0,
    ).update(status=UserPlan.Status.PENDING_RELEASE, unlocked_at=ir_now())

    # update user plans that wanna renew
    UserPlan.objects.filter(plan_id=plan_id, status=UserPlan.Status.LOCKED, locked_amount__gt=0,).update(
        status=UserPlan.Status.EXTEND_TO_NEXT_CYCLE,
        extended_to_next_cycle_amount=F('locked_amount'),
    )
