"""StakingTransaction Model: This model is used to track all changes
    on user contribution to staking plan, note that instances of this
    model should not be deleted or edited.
"""
from decimal import ROUND_DOWN, Decimal
from typing import List, Optional

from django.db import models, transaction
from model_utils import Choices

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.decorators import measure_time
from exchange.base.locker import Locker
from exchange.base.validators import validate_transaction_is_atomic
from exchange.staking import errors
from exchange.staking.metrics import Metrics
from exchange.wallet.models import Transaction

from .helpers import add_to_transaction_amount
from .plan import Plan, PlanTransaction

# Defined externally to be used in Meta.constraints
_StakingTransactionTypes = Choices(
    # user actions:
    (10, 'create_request', 'Staking Request'),
    (11, 'cancel_create_request', 'Cancel Create Request'),
    (20, 'end_request', 'End Request'),
    (21, 'cancel_end_request', 'Cancel End Request'),
    (31, 'instant_end_request', 'Instant End Request'),
    (32, 'auto_end_request', 'Auto Extend Request'),
    # system `admin like` actions:
    (112, 'system_accepted_create', 'System Accepted user create request'),
    (113, 'system_rejected_create', 'System Rejected user create request'),
    (122, 'system_accepted_end', 'System Accepted user end staking request'),
    (123, 'system_rejected_end', 'System Rejected user end staking request'),
    # admin actions:
    (213, 'admin_rejected_create', 'System Rejected user create request'),
    (223, 'admin_rejected_end', 'System Rejected user end staking request'),
    # system actions:
    (301, 'announce_reward', 'announce_reward'),
    (302, 'give_reward', 'give_reward'),
    (303, 'stake', 'stake'),
    (304, 'release', 'release'),
    (305, 'unstake', 'unstake'),
    (311, 'extend_out', 'extend_out'),
    (312, 'extend_in', 'extend_in'),
    (999, 'deactivator', 'deactivator'),
)


class StakingTransaction(models.Model):
    TYPES = _StakingTransactionTypes

    user = models.ForeignKey(User, related_name='+', on_delete=models.CASCADE)
    plan = models.ForeignKey(
        Plan, related_name='staking_transactions', related_query_name='staking_transaction', on_delete=models.CASCADE,
    )

    tp = models.SmallIntegerField(choices=TYPES)
    amount = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    parent = models.ForeignKey(
        'self', null=True, default=None, related_name='children', related_query_name='child', on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(default=ir_now)
    plan_transaction = models.ForeignKey(
        PlanTransaction, null=True, default=None, on_delete=models.SET_NULL,
    )
    wallet_transaction = models.ForeignKey(
        Transaction, related_name='+', null=True, default=None, on_delete=models.SET_NULL,
    )

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=('user_id', 'plan_id'),
                condition=models.Q(tp=_StakingTransactionTypes.end_request),
                name='stkng_trx_unique_end_request',
            ),
            models.UniqueConstraint(
                fields=('user_id', 'plan_id'),
                condition=models.Q(
                    models.Q(tp=_StakingTransactionTypes.give_reward)
                    & models.Q(plan_id__gt=297)
                ),
                name='stkng_trx_unique_give_reward',
            ),
        )

    @staticmethod
    @measure_time(metric=Metrics.STAKING_LOCK_WAIT_TIME)
    def get_lock(user_id: int, plan_id: int) -> None:
        validate_transaction_is_atomic()
        Locker.require_lock(f'staking_lock_{plan_id}', user_id)

    @classmethod
    def get_active_transaction_by_tp(cls, user_id: int, plan_id: int, tp: int) -> 'StakingTransaction':
        return cls.objects.get(user_id=user_id, plan_id=plan_id, child=None, tp=tp)

    @classmethod
    def does_transaction_exists(cls, user_id: int, plan_id: int, types: List[int]) -> bool:
        return cls.objects.filter(user_id=user_id, plan_id=plan_id, tp__in=types).exists()

    @classmethod
    def _cancel_or_reject_end_request(
        cls, user_id: int, plan_id: int, amount: Decimal, tp: int
    ) -> 'StakingTransaction':
        if tp not in (
            StakingTransaction.TYPES.cancel_end_request,
            StakingTransaction.TYPES.admin_rejected_end,
        ):
            raise errors.InvalidType('Invalid type')

        if amount <= Decimal('0'):
            raise errors.InvalidAmount('Amount is too low.')

        cls.get_lock(user_id, plan_id)
        try:
            staking_transaction = cls.get_active_transaction_by_tp(user_id, plan_id, StakingTransaction.TYPES.stake)
        except cls.DoesNotExist:
            raise errors.ParentIsNotCreated('user has no active staking in plan')

        try:
            unstake_request = cls.objects.get(
                user_id=user_id,
                plan_id=plan_id,
                tp=cls.TYPES.unstake,
                amount=amount,
                child=None,
            )
        except cls.DoesNotExist as e:
            raise errors.ParentIsNotCreated('There is no instant end request to reject with specified amount.') from e

        plan = Plan.get_plan_to_update(plan_id)
        plan.block_capacity(unstake_request.amount)

        add_to_transaction_amount(unstake_request, -amount)
        add_to_transaction_amount(staking_transaction, amount)
        cancel_or_reject_request = StakingTransaction.objects.create(
            user_id=user_id,
            plan_id=plan_id,
            parent=unstake_request,
            tp=tp,
            amount=amount,
        )
        return cancel_or_reject_request

    @classmethod
    @transaction.atomic
    def admin_reject_end_staking_request(cls, user_id: int, plan_id: int, amount: Decimal) -> 'StakingTransaction':
        return cls._cancel_or_reject_end_request(user_id, plan_id, amount, cls.TYPES.admin_rejected_end)

    @classmethod
    def active_requests(cls, user_id: int, plan_type: Optional[int]) -> 'models.QuerySet[StakingTransaction]':
        query = cls.objects.filter(
            user_id=user_id,
            child=None,
            tp__in=[
                cls.TYPES.create_request,
                cls.TYPES.end_request,
                cls.TYPES.auto_end_request,
                cls.TYPES.instant_end_request,
            ],
        ).select_related('plan', 'plan__external_platform')
        if plan_type is not None:
            query = query.filter(plan__external_platform__tp=plan_type)
        return query

    @classmethod
    def add_to_stake_amount(cls, user_id: int, plan_id: int, amount: Decimal) -> None:
        try:
            stake_transaction = cls.get_active_transaction_by_tp(user_id, plan_id, cls.TYPES.stake)
            stake_transaction.amount += amount
            stake_transaction.save(update_fields=('amount',))
        except cls.DoesNotExist:
            cls.objects.create(
                user_id=user_id,
                plan_id=plan_id,
                tp=cls.TYPES.stake,
                amount=amount,
            )

    @classmethod
    @transaction.atomic
    def enable_auto_end(cls, user_id: int, plan_id: int) -> None:
        cls.get_lock(user_id, plan_id)
        plan = Plan.get_plan_to_read(plan_id)
        if ir_now() > plan.staked_at + plan.staking_period:
            raise errors.TooLate('Cant disable auto extend for ended plan.')

        if not plan.is_extendable:
            raise errors.NonExtendablePlan('Cant set auto-extend flag for un-extendable Plan.')
        try:
            cls.get_active_transaction_by_tp(user_id, plan_id, cls.TYPES.auto_end_request)
        except cls.DoesNotExist:
            cls.objects.create(user_id=user_id, plan_id=plan_id, tp=cls.TYPES.auto_end_request)

    @classmethod
    @transaction.atomic
    def disable_auto_end(cls, user_id: int, plan_id: int) -> None:
        cls.get_lock(user_id, plan_id)
        plan = Plan.get_plan_to_read(plan_id)

        if not plan.is_extendable:
            raise errors.NonExtendablePlan('Cant set auto-extend flag for un-extendable Plan.')

        if ir_now() > plan.staked_at + plan.staking_period:
            raise errors.TooLate('Cant enable auto extend for ended plan.')

        try:
            request = cls.get_active_transaction_by_tp(user_id, plan_id, cls.TYPES.auto_end_request)
        except cls.DoesNotExist:
            return
        cls.objects.create(user_id=user_id, plan_id=plan_id, tp=cls.TYPES.deactivator, parent=request)
