from decimal import Decimal
from typing import Optional, Tuple

from django.db import transaction
from django.utils.timezone import timedelta

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from exchange.staking import errors
from exchange.staking.errors import InvalidPlanId, run_safely_with_exception_report
from exchange.staking.helpers import StakingFeatureFlags, check_wallet_balance
from exchange.staking.models import (
    ExternalEarningPlatform,
    Plan,
    StakingTransaction,
    UserPlan,
    UserPlanRequest,
    UserPlanWalletTransaction,
)
from exchange.staking.service.auto_renewal import set_plan_auto_renewal
from exchange.wallet.helpers import RefMod, create_and_commit_transaction
from exchange.wallet.models import Transaction


@transaction.atomic
def subscribe(user: User, plan_id: int, amount: Decimal, allow_renewal: Optional[bool] = False) -> StakingTransaction:
    check_wallet_balance(user.id, Plan.get_plan_currency(plan_id), amount)
    if amount <= Decimal('0'):
        raise errors.InvalidAmount('Invalid amount.')

    # legacy code marked for removal -> check_user_plan_request
    StakingTransaction.get_lock(user.id, plan_id)
    if StakingTransaction.objects.filter(
        user_id=user.id,
        plan_id=plan_id,
        tp__in=(StakingTransaction.TYPES.cancel_create_request, StakingTransaction.TYPES.admin_rejected_create),
        created_at__gte=ir_now() - timedelta(days=1),
    ).exists():
        raise errors.RecentlyCanceled('`Recently canceled request` restriction.')
    ###############################

    plan = Plan.get_plan_to_update(plan_id)
    plan.check_if_plan_is_open_to_accepting_requests()
    amount = plan.quantize_amount(amount)
    plan.block_capacity(amount)

    # legacy code marked for removal
    try:
        current_request = StakingTransaction.get_active_transaction_by_tp(
            user.id, plan_id, StakingTransaction.TYPES.create_request
        )
        new_amount = current_request.amount + amount
    except StakingTransaction.DoesNotExist:
        current_request = None
        new_amount = amount

    request = StakingTransaction.objects.create(
        user_id=user.id,
        plan_id=plan_id,
        parent=current_request,
        tp=StakingTransaction.TYPES.create_request,
        amount=new_amount,
    )
    ###############################
    user_plan_subscription = create_user_plan_subscription(user=user, plan=plan, amount=amount)

    try:
        wallet_transaction = create_and_commit_transaction(
            user_id=user.id,
            currency=plan.currency,
            amount=-amount,
            ref_id=request.id,
            ref_module={
                ExternalEarningPlatform.TYPES.staking: RefMod.staking_request,
                ExternalEarningPlatform.TYPES.yield_aggregator: RefMod.yield_farming_request,
            }.get(plan.external_platform.tp),
            description=f'درخواست مشارکت در {plan.fa_description}',
        )
    except ValueError as e:
        raise errors.FailedAssetTransfer('Invalid wallet of insufficient balance.') from e
    request.wallet_transaction = wallet_transaction
    request.save(update_fields=('wallet_transaction',))

    if user_plan_subscription:
        create_user_plan_wallet_transaction(
            user_plan=user_plan_subscription[0],
            user_request=user_plan_subscription[1],
            withdraw_wallet_transaction=wallet_transaction,
        )

    set_plan_auto_renewal(plan_id=plan.id, user_id=user.id, allow_renewal=allow_renewal)
    return request


def check_user_plan_request(user_id: int, plan_id: int):
    if UserPlanRequest.objects.filter(
        user_plan__user_id=user_id,
        user_plan__plan_id=plan_id,
        status__in=(UserPlanRequest.Status.USER_CANCELLED, UserPlan.Status.ADMIN_REJECTED),
        tp=UserPlanRequest.Type.SUBSCRIPTION,
        created_at__gte=ir_now() - timedelta(days=1),
    ).exists():
        raise errors.RecentlyCanceled('`Recently canceled request` restriction.')


@run_safely_with_exception_report
def create_user_plan_subscription(
    user: User, plan: Plan, amount: Decimal
) -> Tuple[Optional[UserPlan], Optional[UserPlanRequest]]:
    if not Settings.get_flag(StakingFeatureFlags.API_DUAL_WRITE):
        return None, None

    check_user_plan_request(user.id, plan.id)

    try:
        user_plan = UserPlan.objects.select_for_update(of=('self',)).get(
            user=user,
            plan=plan,
        )

        if user_plan.status not in UserPlan.ALLOW_ADD_SUBSCRIPTION_STATUS:
            raise InvalidPlanId()

        user_plan.requested_amount += amount
        user_plan.locked_amount += amount
        user_plan.save(update_fields=['requested_amount', 'locked_amount'])
    except UserPlan.DoesNotExist:
        user_plan = UserPlan.objects.create(
            user=user,
            plan=plan,
            status=UserPlan.Status.REQUESTED,
            requested_amount=amount,
            locked_amount=amount,
        )

    user_request = UserPlanRequest.objects.create(
        user_plan=user_plan,
        amount=amount,
        tp=UserPlanRequest.Type.SUBSCRIPTION,
        status=UserPlanRequest.Status.CREATED,
    )

    return user_plan, user_request


@run_safely_with_exception_report
def create_user_plan_wallet_transaction(
    user_plan: UserPlan, user_request: UserPlanRequest, withdraw_wallet_transaction: Transaction
):
    if not Settings.get_flag(StakingFeatureFlags.API_DUAL_WRITE):
        return

    UserPlanWalletTransaction.objects.create(
        user_plan=user_plan,
        amount=withdraw_wallet_transaction.amount,
        tp=UserPlanWalletTransaction.Type.SUBSCRIPTION,
        wallet_transaction=withdraw_wallet_transaction,
        user_plan_request=user_request,
    )
