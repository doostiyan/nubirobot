from django.db import transaction

from exchange.base.logging import report_exception
from exchange.base.models import Settings
from exchange.staking import errors
from exchange.staking.admin_notifier import notify_or_raise_exception_decorator
from exchange.staking.errors import InvalidPlanId, run_safely_with_exception_report
from exchange.staking.helpers import StakingFeatureFlags
from exchange.staking.models import (
    ExternalEarningPlatform,
    Plan,
    PlanTransaction,
    StakingTransaction,
    UserPlan,
    UserPlanWalletTransaction,
)
from exchange.wallet.helpers import RefMod, create_and_commit_transaction


def pay_all_users_reward(plan_id: int):
    _create_staking_rewards_transactions(plan_id)


def _create_staking_rewards_transactions(plan_id: int):
    for user_id in Plan.get_plan_user_ids_to_pay_reward(plan_id):
        try:
            notify_or_raise_exception_decorator(_pay_user_reward)(user_id, plan_id)
        except Exception:
            report_exception()


@transaction.atomic
def _pay_user_reward(user_id: int, plan_id: int) -> None:
    StakingTransaction.get_lock(user_id, plan_id)
    try:
        user_last_announced_reward = StakingTransaction.get_active_transaction_by_tp(
            user_id, plan_id, StakingTransaction.TYPES.announce_reward
        )
    except StakingTransaction.DoesNotExist as e:
        if StakingTransaction.does_transaction_exists(user_id, plan_id, types=[StakingTransaction.TYPES.give_reward]):
            raise errors.AlreadyCreated('Already payed reward.') from e
        raise errors.ParentIsNotCreated('Cant pay reward when there is no reward announcement.') from e

    plan = Plan.get_plan_to_update(plan_id)
    if not user_last_announced_reward.created_at == plan.staked_at + plan.staking_period:
        raise errors.TooSoon('Too soon to pay rewards.')

    try:
        plan_reward_transaction = plan.get_active_transaction_by_tp(PlanTransaction.TYPES.give_reward)
    except PlanTransaction.DoesNotExist as e:
        raise errors.PlanTransactionIsNotCreated(
            'Cant pay users reward since Plan reward has not been withdrawn yet.',
        ) from e

    if plan_reward_transaction.amount < user_last_announced_reward.amount:
        raise errors.InvalidAmount(
            f'Plan reward amount is not enough to pay user #{user_id} reward of plan #{plan_id}.',
        )

    user_give_reward_transaction = StakingTransaction.objects.create(
        user_id=user_id,
        plan_id=plan_id,
        amount=user_last_announced_reward.amount,
        created_at=user_last_announced_reward.created_at,
        tp=StakingTransaction.TYPES.give_reward,
    )
    try:
        wallet_transaction = create_and_commit_transaction(
            user_id=user_id,
            currency=plan.currency,
            amount=user_last_announced_reward.amount,
            ref_id=user_give_reward_transaction.id,
            ref_module={
                ExternalEarningPlatform.TYPES.staking: RefMod.staking_reward,
                ExternalEarningPlatform.TYPES.yield_aggregator: RefMod.yield_farming_reward,
            }.get(plan.external_platform.tp),
            description=f'پاداش {plan.fa_description}.',
        )
    except ValueError as e:
        raise errors.UserWithNegativeBalanceOrDeactivatedWallet(
            f'cant pay user reward for plan #{plan_id}.'
            f' user #{user_id} has negative balance or deactivated wallet.',
        ) from e

    _pay_user_plan_reward(
        user_id=user_id,
        plan_id=plan_id,
        user_reward_deposit_transaction=wallet_transaction,
    )

    plan_reward_transaction.amount -= user_last_announced_reward.amount
    plan_reward_transaction.save(update_fields=('amount',))
    user_give_reward_transaction.wallet_transaction = wallet_transaction
    user_give_reward_transaction.save(update_fields=('wallet_transaction',))


@run_safely_with_exception_report
@transaction.atomic
def _pay_user_plan_reward(user_id: int, plan_id: int, user_reward_deposit_transaction):
    if not Settings.get_flag(StakingFeatureFlags.CRONJOB_DUAL_WRITE):
        return

    # StakingTransaction.get_lock(user_id, plan_id) todo
    try:
        user_plan = UserPlan.objects.select_for_update(of=('self',)).get(
            status__in=[
                UserPlan.Status.EXTEND_TO_NEXT_CYCLE,
                UserPlan.Status.PENDING_RELEASE,
                UserPlan.Status.RELEASED,
                # we must be after staking period,
                # so locked status is not accepted
            ],
            user_id=user_id,
            plan_id=plan_id,
            locked_amount__gt=0,
            reward_amount__gt=0,
        )

    except UserPlan.DoesNotExist as e:
        raise InvalidPlanId() from e

    if UserPlanWalletTransaction.objects.filter(user_plan=user_plan, tp=UserPlanWalletTransaction.Type.REWARD).exists():
        raise errors.AlreadyCreated('Already payed reward.')

    plan = Plan.get_plan_to_update(plan_id)

    try:
        plan_reward_transaction = plan.get_active_transaction_by_tp(PlanTransaction.TYPES.give_reward)
    except PlanTransaction.DoesNotExist as e:
        raise errors.PlanTransactionIsNotCreated(
            'Cant pay users reward since Plan reward has not been withdrawn yet.',
        ) from e

    if plan_reward_transaction.created_at < plan.staked_at + plan.staking_period:
        raise errors.TooSoon('Too soon to pay rewards.')

    if plan_reward_transaction.amount < user_plan.reward_amount:
        raise errors.InvalidAmount(
            f'Plan reward amount is not enough to pay user #{user_id} reward of plan #{plan_id}.',
        )

    UserPlanWalletTransaction.objects.create(
        user_plan=user_plan,
        wallet_transaction=user_reward_deposit_transaction,
        amount=user_plan.reward_amount,
        tp=UserPlanWalletTransaction.Type.REWARD,
    )
