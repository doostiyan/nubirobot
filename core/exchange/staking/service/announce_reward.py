from decimal import ROUND_DOWN, Decimal

from django.db import transaction

from exchange.base.models import Settings
from exchange.staking.errors import AlreadyCreated, run_safely_with_exception_report
from exchange.staking.helpers import StakingFeatureFlags
from exchange.staking.models import Plan, PlanTransaction, StakingTransaction, UserPlan


@transaction.atomic
def announce_all_users_rewards(plan_id: int) -> None:
    plan = Plan.get_plan_to_update(plan_id)
    announcement_timestamp = plan.get_reward_announcement_timestamp()

    try:
        last_announcement_transaction = plan.get_active_transaction_by_tp(
            tp=PlanTransaction.TYPES.announce_reward,
        )
        last_announcement_transaction_amount = last_announcement_transaction.amount
    except PlanTransaction.DoesNotExist:
        last_announcement_transaction = None
        last_announcement_transaction_amount = Decimal('0')

    if last_announcement_transaction and last_announcement_transaction.created_at == announcement_timestamp:
        raise AlreadyCreated(f'Repetitive announce reward attempt for plan #{plan_id}.')

    reward_amount_after_fee = last_announcement_transaction_amount + (
        plan.get_fetched_reward_amount_until(announcement_timestamp)
        - plan.get_fetched_reward_amount_until(announcement_timestamp - plan.reward_announcement_period)
    ) * (Decimal(1) - plan.fee)

    announcement_transaction = PlanTransaction.objects.create(
        plan=plan,
        created_at=announcement_timestamp,
        tp=PlanTransaction.TYPES.announce_reward,
        amount=reward_amount_after_fee,
        parent=last_announcement_transaction,
    )
    _create_users_announce_reward_transactions(plan, announcement_transaction)
    _update_user_plan_rewards(plan, announcement_transaction)


@transaction.atomic
def edit_last_announced_reward(plan_id: int, amount: Decimal) -> None:
    plan = Plan.get_plan_to_update(plan_id)
    announcement_transaction = plan.get_active_transaction_by_tp(tp=PlanTransaction.TYPES.announce_reward)
    announcement_transaction.amount = amount
    announcement_transaction.save(update_fields=('amount',))
    _edit_users_announce_reward_transactions(plan, announcement_transaction)
    _update_user_plan_rewards(plan, announcement_transaction)


def _edit_users_announce_reward_transactions(plan: Plan, plan_announce_reward_transaction: PlanTransaction) -> None:
    user_ids = Plan.get_plan_user_ids(plan.id)
    user_id_to_staking_amount_map = dict(
        list(
            StakingTransaction.objects.filter(
                user_id__in=user_ids,
                plan=plan,
                tp=StakingTransaction.TYPES.stake,
            ).values_list('user_id', 'amount')
        )
    )

    staking_announce_reward_transactions = StakingTransaction.objects.filter(
        plan_transaction=plan_announce_reward_transaction
    )
    for trx in staking_announce_reward_transactions:
        if user_id_to_staking_amount_map.get(trx.user_id):
            trx.amount = (
                plan_announce_reward_transaction.amount
                * (user_id_to_staking_amount_map.get(trx.user_id) / plan.total_capacity)
            ).quantize(Decimal('1E-10'), ROUND_DOWN)
    StakingTransaction.objects.bulk_update(staking_announce_reward_transactions, fields=('amount',))


def _create_users_announce_reward_transactions(plan: Plan, plan_announce_reward_transaction: PlanTransaction) -> None:
    user_ids = Plan.get_plan_user_ids(plan.id)
    user_id_to_parent_transaction_map = dict(
        list(
            StakingTransaction.objects.filter(
                user_id__in=user_ids,
                plan=plan,
                tp=StakingTransaction.TYPES.announce_reward,
                child=None,
            ).values_list('user_id', 'id')
        )
    )
    user_id_to_staking_amount_map = dict(
        list(
            StakingTransaction.objects.filter(
                user_id__in=user_ids,
                plan=plan,
                tp=StakingTransaction.TYPES.stake,
            ).values_list('user_id', 'amount')
        )
    )

    StakingTransaction.objects.bulk_create(
        StakingTransaction(
            user_id=user_id,
            plan=plan,
            tp=StakingTransaction.TYPES.announce_reward,
            created_at=plan_announce_reward_transaction.created_at,
            plan_transaction=plan_announce_reward_transaction,
            amount=(
                plan_announce_reward_transaction.amount
                * (user_id_to_staking_amount_map.get(user_id) / plan.total_capacity)
            ).quantize(Decimal('1E-10'), ROUND_DOWN),
            parent_id=user_id_to_parent_transaction_map.get(user_id),
        )
        for user_id in user_ids
        if user_id_to_staking_amount_map.get(user_id)
    )


@run_safely_with_exception_report
@transaction.atomic
def _update_user_plan_rewards(plan: Plan, plan_announce_reward_transaction: PlanTransaction):
    if not Settings.get_flag(StakingFeatureFlags.CRONJOB_DUAL_WRITE):
        return

    user_plans = UserPlan.objects.filter(plan=plan).exclude(
        status__in=[
            UserPlan.Status.REQUESTED,
            UserPlan.Status.ADMIN_REJECTED,
            UserPlan.Status.USER_CANCELED,
        ]
    )

    for user_plan in user_plans:
        user_plan.reward_amount = (
            plan_announce_reward_transaction.amount * (user_plan.locked_amount / plan.total_capacity)
        ).quantize(Decimal('1E-10'), ROUND_DOWN)

    UserPlan.objects.bulk_update(user_plans, fields=('reward_amount',))
