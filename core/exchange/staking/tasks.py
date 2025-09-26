"""Staking Tasks"""
from decimal import Decimal

from celery import shared_task

from exchange.base.decorators import measure_time_cm
from exchange.base.logging import report_exception
from exchange.base.parsers import parse_float, parse_int, parse_money
from exchange.staking import errors, rewards
from exchange.staking.admin_notifier import notify_or_raise_exception_decorator
from exchange.staking.metrics import Metrics
from exchange.staking.models import Plan, StakingTransaction
from exchange.staking.service.announce_reward import announce_all_users_rewards
from exchange.staking.service.announce_reward import edit_last_announced_reward as edit_last_announced_reward_service
from exchange.staking.service.auto_renewal import set_plan_auto_renewal
from exchange.staking.service.extend_staking import extend_all_users_staking
from exchange.staking.service.instant_end import add_and_apply_instant_end_request
from exchange.staking.service.pay_rewards import pay_all_users_reward
from exchange.staking.service.end_staking import end_all_users_staking
from exchange.staking.service.reject_requests.subscription import reject_user_subscription
from exchange.staking.service.release_assets import release_all_users_assets
from exchange.staking.service.stake_assets import stake_all_users_assets


@shared_task(name='staking.admin.reject_user_request')
def reject_user_request_task(
    user_id: int,
    plan_id: int,
    amount: str,
    tp: str,
) -> None:
    user_id = parse_int(user_id, required=True)
    plan_id = parse_int(plan_id, required=True)
    amount = parse_money(amount, required=True)
    if tp not in (
        'reject_create',
        'reject_end',
    ):
        raise errors.AdminMistake(f'Admin is calling `reject_user_request` with invalid `tp` argument: \'{tp}\'.')

    if tp == 'reject_create':
        reject_user_subscription(user_id, plan_id, amount)

    if tp == 'reject_end':
        StakingTransaction.admin_reject_end_staking_request(user_id, plan_id, amount)


@shared_task(name='staking.admin.edit_last_announced_reward')
def edit_last_announced_reward(plan_id: int, amount: str,) -> None:
    plan_id = parse_int(plan_id, required=True)
    amount = Decimal(str(parse_float(amount, required=True)))
    edit_last_announced_reward_service(plan_id, amount)


@shared_task(name='staking.admin.edit_last_announced_reward_and_pay_users_rewards')
def edit_last_announced_reward_and_pay_users_rewards_task(plan_id: int, amount: str,) -> None:
    plan_id = parse_int(plan_id, required=True)
    amount = parse_money(amount, required=True)
    edit_last_announced_reward_service(plan_id, amount)
    try:
        Plan.approve_reward_amount(plan_id,)
    except Exception:
        report_exception()
    Plan.withdraw_users_reward_from_plan(plan_id,)


@shared_task(name='staking.admin.create_instant_end_request')
def creating_an_instant_cancellation_request_task(user_id: int, plan_id: int, amount: str) -> None:
    user_id = parse_int(user_id, required=True)
    plan_id = parse_int(plan_id, required=True)
    amount = parse_money(amount, required=True)
    add_and_apply_instant_end_request(user_id=user_id, plan_id=plan_id, amount=amount, created_by_admin=True)


@shared_task(name='staking.admin.enable_auto_extend')
def enable_auto_extend_task(user_id: int, plan_id: int) -> None:
    user_id = parse_int(user_id, required=True)
    plan_id = parse_int(plan_id, required=True)
    set_plan_auto_renewal(plan_id=plan_id, user_id=user_id, allow_renewal=True)


@shared_task(name='staking.admin.disable_auto_extend')
def disable_auto_extend_task(user_id: int, plan_id: int) -> None:
    user_id = parse_int(user_id, required=True)
    plan_id = parse_int(plan_id, required=True)
    set_plan_auto_renewal(plan_id=plan_id, user_id=user_id, allow_renewal=False)


@shared_task(name='staking.core.stake_assets')
@notify_or_raise_exception_decorator
@measure_time_cm(metric=str(Metrics.TASK_STAKE_ASSETS_TIME))
def stake_assets_task(plan_id: int):
    Plan.stake_assets(plan_id)


@shared_task(name='staking.core.assign_staking_to_users')
@measure_time_cm(metric=str(Metrics.TASK_ASSIGN_USER_STAKING_TIME))
def assign_staking_to_users_task(plan_id: int):
    stake_all_users_assets(plan_id)


@shared_task(name='staking.core.end_users_staking')
@measure_time_cm(metric=str(Metrics.TASK_END_USER_STAKING_TIME))
def end_users_staking_task(plan_id: int):
    end_all_users_staking(plan_id)


@shared_task(name='staking.core.create_release_transaction')
@notify_or_raise_exception_decorator
@measure_time_cm(metric=str(Metrics.TASK_CREATE_RELEASE_TRX_TIME))
def create_release_transaction_task(plan_id: int):
    Plan.create_release_transaction(plan_id)


@shared_task(name='staking.core.release_users_assets')
@measure_time_cm(metric=str(Metrics.TASK_RELEASE_USER_ASSETS_TIME))
def release_users_assets_task(plan_id: int):
    release_all_users_assets(plan_id)


@shared_task(name='staking.core.system_approve_stake_amount')
@notify_or_raise_exception_decorator
@measure_time_cm(metric=str(Metrics.TASK_SYSTEM_APPROVE_STAKE_AMOUNT_TIME))
def system_approve_stake_amount_task(plan_id: int):
    Plan.system_approve_stake_amount(plan_id,)


@shared_task(name='staking.core.fetch_reward')
@notify_or_raise_exception_decorator
@measure_time_cm(metric=str(Metrics.TASK_FETCH_REWARD_TIME))
def fetch_reward_task(plan_id: int):
    rewards.fetch_reward(plan_id)


@shared_task(name='staking.core.announce_rewards')
@notify_or_raise_exception_decorator
@measure_time_cm(metric=str(Metrics.TASK_ANNOUNCE_REWARD_TIME))
def announce_rewards_task(plan_id: int,):
    announce_all_users_rewards(plan_id)


@shared_task(name='staking.core.pay_rewards')
@measure_time_cm(metric=str(Metrics.TASK_PAY_REWARD_TIME))
def pay_rewards_task(plan_id: int):
    pay_all_users_reward(plan_id)


@shared_task(name='staking.core.create_extend_out_transaction')
@notify_or_raise_exception_decorator
@measure_time_cm(metric=str(Metrics.TASK_CREATE_EXTEND_OUT_TIME))
def create_extend_out_transaction_task(plan_id: int,):
    Plan.create_extend_out_transaction(plan_id)


@shared_task(name='staking.core.create_extend_in_transaction')
@notify_or_raise_exception_decorator
@measure_time_cm(metric=str(Metrics.TASK_CREATE_EXTEND_IN_TIME))
def create_extend_in_transaction_task(plan_id: int,):
    Plan.create_extend_in_transaction(plan_id)


@shared_task(name='staking.core.extend_stakings')
@measure_time_cm(metric=str(Metrics.TASK_EXTEND_STAKING_TIME))
def extend_stakings_task(plan_id: int,):
    extend_all_users_staking(plan_id)
