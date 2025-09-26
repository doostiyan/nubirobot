from decimal import Decimal

from django.db import transaction

from exchange.base.logging import report_exception
from exchange.base.models import Settings
from exchange.staking import errors
from exchange.staking.admin_notifier import notify_or_raise_exception_decorator
from exchange.staking.errors import InvalidPlanId, InvalidUserPlanExtension, run_safely_with_exception_report
from exchange.staking.helpers import StakingFeatureFlags
from exchange.staking.models import Plan, PlanTransaction, StakingTransaction, UserPlan


def extend_all_users_staking(plan_id: int):
    _create_extend_in_transactions(plan_id)


def _create_extend_in_transactions(plan_id: int):
    for user_id in Plan.get_user_ids_to_extend(plan_id):
        try:
            notify_or_raise_exception_decorator(_extend_user_staking)(user_id, plan_id)
            _extend_user_plan(user_id, plan_id)
        except Exception:
            report_exception()


@transaction.atomic
def _extend_user_staking(user_id: int, plan_id: int) -> None:
    """By calling this method staking of user in plan with `plan_id` will
    be transferred to extension the extension plan.
    """
    StakingTransaction.get_lock(user_id, plan_id)
    try:
        extend_out_transaction = StakingTransaction.get_active_transaction_by_tp(
            user_id, plan_id, StakingTransaction.TYPES.extend_out
        )
    except StakingTransaction.DoesNotExist as e:
        if StakingTransaction.does_transaction_exists(user_id, plan_id, types=[StakingTransaction.TYPES.extend_out]):
            raise errors.UserStakingAlreadyExtended('Staking has already been extended.') from e
        raise errors.ParentIsNotCreated('Previous plan has not been extended yet.') from e

    if extend_out_transaction.amount == Decimal('0'):
        StakingTransaction.objects.create(
            user_id=user_id,
            plan_id=plan_id,
            tp=StakingTransaction.TYPES.deactivator,
            parent=extend_out_transaction,
        )
        return

    plan = Plan.get_plan_to_update(plan_id)
    extension_plan = plan.get_extension()
    try:
        plan_transaction = extension_plan.get_active_transaction_by_tp(PlanTransaction.TYPES.extend_in)
    except PlanTransaction.DoesNotExist as e:
        raise errors.PlanTransactionIsNotCreated('No plan extension transaction.') from e

    StakingTransaction.objects.create(
        user_id=user_id,
        plan_id=extension_plan.id,
        tp=StakingTransaction.TYPES.extend_in,
        amount=extend_out_transaction.amount,
        parent=extend_out_transaction,
        plan_transaction=plan_transaction,
    )
    StakingTransaction.add_to_stake_amount(user_id, extension_plan.id, extend_out_transaction.amount)
    extension_plan.add_to_stake_amount(-extend_out_transaction.amount)


@run_safely_with_exception_report
@transaction.atomic
def _extend_user_plan(user_id: int, plan_id: int):
    if not Settings.get_flag(StakingFeatureFlags.CRONJOB_DUAL_WRITE):
        return

    # StakingTransaction.get_lock(user_id, plan_id) # todo

    try:
        user_plan = UserPlan.objects.select_for_update(of=('self',)).get(
            user_id=user_id,
            plan_id=plan_id,
            status=UserPlan.Status.EXTEND_TO_NEXT_CYCLE,
            next_cycle__isnull=True,
        )
    except UserPlan.DoesNotExist as _:
        raise InvalidUserPlanExtension('Previous UserPlan has not been extended yet or status changed.')

    if user_plan.extended_to_next_cycle_amount <= 0:
        # we are raising this error because the user plan must
        # be released or extended with some valid amount, and
        # if this happens, this is potentially a bug
        raise InvalidUserPlanExtension(f'UserPlan #{user_plan.id} with zero extension amount')

    plan = Plan.get_plan_to_update(plan_id)
    extension_plan = plan.get_extension()
    extension_plan.get_active_transaction_by_tp(PlanTransaction.TYPES.extend_in)

    try:
        extension_user_plan = _get_next_cycle_requested_user_plan(user_id=user_id, extension_plan_id=extension_plan.id)
        extension_user_plan.locked_amount += user_plan.extended_to_next_cycle_amount
        extension_user_plan.extended_from_previous_cycle_amount = user_plan.extended_to_next_cycle_amount
        extension_user_plan.save(update_fields=['locked_amount', 'extended_from_previous_cycle_amount'])
    except UserPlan.DoesNotExist as _:
        extension_user_plan = UserPlan.objects.create(
            user_id=user_id,
            plan_id=extension_plan.id,
            status=UserPlan.Status.EXTEND_FROM_PREVIOUS_CYCLE,
            locked_amount=user_plan.extended_to_next_cycle_amount,
            extended_from_previous_cycle_amount=user_plan.extended_to_next_cycle_amount,
        )

    user_plan.next_cycle = extension_user_plan
    user_plan.save(update_fields=['next_cycle'])


def _get_next_cycle_requested_user_plan(user_id: int, extension_plan_id: int) -> UserPlan:
    """Users can request in next plan when it opens and have a requested user plan."""

    next_cycle_user_plan = UserPlan.objects.select_for_update(of=('self',)).get(
        user_id=user_id,
        plan_id=extension_plan_id,
    )
    if next_cycle_user_plan.status != UserPlan.Status.REQUESTED:
        raise InvalidUserPlanExtension(
            f'Existing next plan, User #{extension_plan_id}, Plan #{extension_plan_id} with invalid status'
        )

    return next_cycle_user_plan
