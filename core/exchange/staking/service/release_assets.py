from django.db import models, transaction
from django.utils.timezone import timedelta

from exchange.base.calendar import ir_now
from exchange.base.logging import report_exception
from exchange.staking.admin_notifier import notify_or_raise_exception_decorator
from exchange.staking.models import ExternalEarningPlatform, Plan, StakingTransaction
from exchange.wallet.helpers import RefMod, create_and_commit_transaction


def release_all_users_assets(plan_id: int):
    _create_release_staking_transactions(plan_id)


def _create_release_staking_transactions(plan_id: int):
    for user_id in Plan.get_plan_user_ids_of_users_with_unreleased_assets(plan_id):
        try:
            notify_or_raise_exception_decorator(_release_user_asset)(user_id, plan_id)
        except Exception:
            report_exception()


@transaction.atomic
def _release_user_asset(user_id: int, plan_id: int) -> None:
    """After ending of a plan, and after blocking time, it is time
    to give users their initially staked assets back.
    """
    plan = Plan.get_plan_to_read(plan_id)
    StakingTransaction.get_lock(user_id, plan_id)
    for unstake_transaction in _get_unstake_transactions_to_release(user_id, plan_id, plan.unstaking_period):
        release_transaction = StakingTransaction.objects.create(
            user_id=user_id,
            plan_id=plan_id,
            tp=StakingTransaction.TYPES.release,
            amount=unstake_transaction.amount,
            parent=unstake_transaction,
        )

        release_transaction.wallet_transaction = create_and_commit_transaction(
            user_id=user_id,
            currency=plan.currency,
            amount=release_transaction.amount,
            ref_id=release_transaction.id,
            ref_module={
                ExternalEarningPlatform.TYPES.staking: RefMod.staking_release,
                ExternalEarningPlatform.TYPES.yield_aggregator: RefMod.yield_farming_release,
            }.get(plan.external_platform.tp),
            description=f'بازگشت دارایی {plan.fa_description}.',
        )
        release_transaction.save(update_fields=('wallet_transaction',))


def _get_unstake_transactions_to_release(user_id: int, plan_id: int, plan_unstaking_period: timedelta):
    return StakingTransaction.objects.filter(
        user_id=user_id, plan_id=plan_id, tp=StakingTransaction.TYPES.unstake, child=None
    ).filter(
        models.Q(
            ~models.Q(parent__tp=StakingTransaction.TYPES.instant_end_request),
            created_at__lt=ir_now() - plan_unstaking_period,
        )
        | models.Q(
            parent__tp=StakingTransaction.TYPES.instant_end_request,
            created_at__lt=ir_now(),
        )
    )
