"""Plan and PlanTransaction Model:
    Plan is Used to define how users could contribute to
    an external staking.
    PlanTransaction is being used record event and actions
    related to some Plan, note that PlanTransaction should
    not be deleted or edited.
"""

from datetime import datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from typing import List

from django.core.exceptions import MultipleObjectsReturned
from django.db import models, transaction
from django.db.models import Case, F, Q, When
from model_utils import Choices

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.decorators import measure_time, measure_time_cm
from exchange.base.logging import report_exception
from exchange.base.models import get_currency_codename
from exchange.base.strings import _t
from exchange.base.validators import validate_transaction_is_atomic
from exchange.staking import errors
from exchange.staking.helpers import (
    get_asset_collector_user,
    get_fee_collector_user,
    get_nobitex_reward_collector,
)
from exchange.staking.metrics import Metrics
from exchange.wallet.helpers import RefMod, create_and_commit_transaction
from exchange.wallet.models import Transaction
from .external import ExternalEarningPlatform


class Plan(models.Model):
    external_platform = models.ForeignKey(ExternalEarningPlatform, related_name='plans', on_delete=models.CASCADE)
    extended_from = models.ForeignKey(
        'self', related_query_name='extended_to', null=True, default=None, on_delete=models.CASCADE,
    )

    # Initial capacity values:
    total_capacity = models.DecimalField(max_digits=30, decimal_places=10, default=Decimal('0'))
    filled_by_extension = models.DecimalField(max_digits=30, decimal_places=10, default=Decimal('0'))

    # Initially equal to `filled_by_extension`
    filled_capacity = models.DecimalField(max_digits=30, decimal_places=10, default=Decimal('0'))

    # Final capacity values:
    released_capacity = models.DecimalField(max_digits=30, decimal_places=10, default=Decimal('0'))
    extended_capacity = models.DecimalField(max_digits=30, decimal_places=10, default=Decimal('0'))

    # Schedule
    announced_at = models.DateTimeField()
    opened_at = models.DateTimeField()
    request_period = models.DurationField()
    staked_at = models.DateTimeField()  # Should be staked at external earning platform `before` this timestamp
    staking_period = models.DurationField()  # Should be unstaked at external earning platform `after` this timestamp
    unstaking_period = models.DurationField()  # All unstaked Assets should be released `before` this timestamp

    # Config
    fee = models.DecimalField(max_digits=8, decimal_places=8, default=Decimal('0'))
    acceptable_apr_diff = models.DecimalField(max_digits=32, decimal_places=16, default=Decimal('0'))
    estimated_annual_rate = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0'))
    initial_pool_capacity = models.DecimalField(max_digits=30, decimal_places=10)
    is_extendable = models.BooleanField()
    reward_announcement_period = models.DurationField()
    min_staking_amount = models.DecimalField(max_digits=20, decimal_places=10, default=Decimal('0'))
    staking_precision = models.DecimalField(max_digits=12, decimal_places=10, default=Decimal('1E-10'))
    # fixme deprecated field, was used in staking V1, still is used on admin
    is_offer = models.BooleanField(default=False)
    is_instantly_unstakable = models.BooleanField(default=True)

    @property
    def realized_apr(self):
        last_announced_reward = self.transactions.filter(
            tp=PlanTransaction.TYPES.announce_reward,
            child__tp=PlanTransaction.TYPES.give_reward,
        ).first()
        if last_announced_reward is None:
            return Decimal('0')
        return (
            (last_announced_reward.amount / self.total_capacity)
            * Decimal(365 / self.staking_period.days)
            * Decimal('100')
        )

    @property
    def fa_description(self):
        return (
            f'طرح {self.external_platform.type_fa_display} '
            + f'{self.staking_period.days} روزه‌ی {_t(self.currency_codename)}'
        )

    @classmethod
    def check_existence(cls, plan_id: int) -> None:
        if not cls.objects.filter(pk=plan_id).exists():
            raise errors.InvalidPlanId(f"There is no plan with id '{plan_id}'.")

    @classmethod
    def all_plans(cls) -> 'models.QuerySet[Plan]':
        return (
            cls.objects.filter(announced_at__lte=ir_now())
            .annotate(
                is_requestable=Case(
                    When(
                        Q(opened_at__lt=ir_now(), opened_at__gt=ir_now() - F('request_period')),
                        then=1,
                    ),
                    default=0,
                    output_field=models.IntegerField(),
                ),
                closed_at=models.ExpressionWrapper(
                    F('opened_at') + F('request_period'),
                    output_field=models.DateTimeField(),
                ),
            )
            .order_by(
                '-is_requestable',
                '-closed_at',
            )
        )

    @classmethod
    def all_active_plans(cls) -> 'models.QuerySet[Plan]':
        return (
            cls.all_plans()
            .select_related('external_platform')
            .filter(
                external_platform__is_available=True,
                extended_to=None,
                pk__in=Plan.objects.values(
                    'staking_period',
                    'external_platform',
                )
                .annotate(max_id=models.Max('id'))
                .values_list(
                    'max_id',
                    flat=True,
                ),
            )
        )

    @staticmethod
    def filter_by_tp(queryset: 'models.QuerySet[Plan]', tp: int) -> 'models.QuerySet[Plan]':
        return queryset.filter(external_platform__tp=tp).select_related('external_platform')

    @classmethod
    def is_plan_extendable(cls, plan_id: int) -> bool:
        return cls.get_plan_to_read(plan_id).is_extendable

    @classmethod
    @measure_time(metric=Metrics.PLAN_LOCK_WAIT_TIME)
    def get_plan_to_update(cls, plan_id: int) -> 'Plan':
        validate_transaction_is_atomic()
        plan = (
            cls.objects.select_for_update(of=('self',))
            .filter(
                pk=plan_id,
            )
            .select_related('external_platform')
            .first()
        )
        if plan is None:
            raise errors.InvalidPlanId(f"There is no plan with id '{plan_id}'.")
        return plan

    @classmethod
    def get_plan_to_read(cls, plan_id: int) -> 'Plan':
        plan = cls.objects.filter(
            pk=plan_id,
        ).select_related('external_platform').first()
        if plan is None:
            raise errors.InvalidPlanId(f"There is no plan with id '{plan_id}'.")
        return plan

    def block_capacity(self, amount: Decimal) -> None:
        if amount < Decimal('0'):
            raise ValueError()
        return self._block_capacity(amount)

    def unblock_capacity(self, amount: Decimal) -> None:
        if amount < Decimal('0'):
            raise ValueError()
        return self._block_capacity(-amount)

    def _block_capacity(self, amount: Decimal) -> None:
        """Blocking and unblocking of plan capacity."""
        if self.filled_capacity + amount > self.total_capacity:
            raise errors.LowPlanCapacity(f'Plan #{self.id} does not has sufficient capacity.')
        if self.filled_capacity + amount < 0:
            raise errors.LowPlanCapacity(f'Plan #{self.id} does not has sufficient capacity.')

        self.filled_capacity = F('filled_capacity') + amount
        self.save(update_fields=('filled_capacity',))

    def quantize_amount(self, amount: Decimal) -> Decimal:
        """This method convert given `amount` to acceptable amount for user
        contribution in a plan. A Plan have constraints on `minimum`
        and `precision` of user contribution.
        """
        amount = amount.quantize(self.staking_precision.normalize(), ROUND_DOWN)
        if amount < 0:
            raise errors.InvalidAmount(f"Amount is not acceptable. (plan_id: '{self.id}')")

        if amount < self.min_staking_amount and not amount == 0:
            raise errors.InvalidAmount(f"Amount is not acceptable. (plan_id: '{self.id}')")

        return amount

    def check_if_plan_is_open_to_accepting_requests(self) -> None:
        nw = ir_now()
        if nw < self.opened_at:
            raise errors.TooSoon(f'Plan #{self.id} is not open to accept requests.')
        if nw >= self.opened_at + self.request_period:
            raise errors.TooLate(f'Request period of plan #{self.id} is over.')

    @property
    def currency(self):
        return self.external_platform.currency

    @property
    def currency_codename(self):
        return get_currency_codename(self.external_platform.currency)

    @classmethod
    def get_plan_currency(cls, plan_id: int) -> int:
        return cls.get_plan_to_read(plan_id).currency

    def get_active_transaction_by_tp(self, tp: int) -> 'PlanTransaction':
        return self.transactions.get(child=None, tp=tp)

    @classmethod
    def is_stake_amount_approved(cls, plan_id: int):
        return PlanTransaction.objects.filter(
            plan_id=plan_id,
            tp=PlanTransaction.TYPES.system_stake_amount_approval,
        ).exists()

    @classmethod
    @transaction.atomic
    def system_approve_stake_amount(cls, plan_id: int):
        from exchange.staking.models import StakingTransaction
        nw = ir_now()
        plan = cls.get_plan_to_update(plan_id)

        if nw < plan.opened_at + plan.request_period:
            raise errors.TooSoon(f'Plan #{plan_id} is still in request period.')

        if cls.is_stake_amount_approved(plan_id):
            raise errors.AlreadyCreated(f'Staking transaction has been already created for plan #{plan_id}.')

        amount = StakingTransaction.objects.filter(
            plan_id=plan_id,
            child=None,
            tp=StakingTransaction.TYPES.create_request,
        ).aggregate(total=models.Sum('amount')).get('total') or Decimal('0')

        approval_transaction = PlanTransaction.objects.create(
            plan_id=plan.id,
            tp=PlanTransaction.TYPES.system_stake_amount_approval,
            amount=amount,
        )
        wallet_transaction = create_and_commit_transaction(
            user_id=get_asset_collector_user(),
            currency=plan.currency,
            amount=amount,
            ref_module=RefMod.staking_request,
            ref_id=approval_transaction.id,
            description=f'user collected assets to be staked (planId: {plan.id})',
        )
        approval_transaction.wallet_transaction = wallet_transaction
        approval_transaction.save(update_fields=('wallet_transaction',))

    def get_reward_announcement_timestamp(self) -> datetime:
        """Each Plan has parameter `reward_announcement_period`, assuming first staking
            announcement occurs in `staked_at` (with amount 0) we can infer that staking
            announcements should occur in `staked_at + reward_announcement_period`, and,
            `staked_at + 2reward_announcement_period`, `staked_at + 3reward_announcement_period`,
            and, ...! Note That other this announcement we have to create one last
            announcement on  `staked_at + staking_period`.
        """

        # Too low values for `reward_announcement_period` cause constant write on DB
        # (Note that announce reward function insert `1 + #users` transactions).
        if self.reward_announcement_period <= timedelta(minutes=1):
            self.reward_announcement_period = timedelta(days=1)
            self.save()

        nw = ir_now()
        if nw < self.staked_at:
            raise errors.TooSoon(f'Should not announce reward for plan #{self.id} which is not been started yet.')

        if nw >= self.staked_at + self.staking_period:
            return self.staked_at + self.staking_period

        announcement_time = self.staked_at
        for i in range(int(self.staking_period / self.reward_announcement_period) + 1):
            if (
                self.staked_at + i * self.reward_announcement_period <= nw < self.staked_at
                + (i + 1) * self.reward_announcement_period
            ):
                return self.staked_at + i * self.reward_announcement_period

        while announcement_time < self.staked_at + self.staking_period:
            if announcement_time < nw < announcement_time + self.reward_announcement_period:
                return announcement_time
            announcement_time += self.reward_announcement_period

    def get_fetched_reward_amount_until(self, timestamp: datetime) -> Decimal:
        fetched_reward_transaction = PlanTransaction.objects.filter(
            plan=self,
            tp=PlanTransaction.TYPES.fetched_reward,
            created_at__lte=timestamp,
        ).order_by('-created_at').first()
        if fetched_reward_transaction is None:
            return Decimal('0')
        return fetched_reward_transaction.amount


    @classmethod
    @transaction.atomic
    def create_extend_out_transaction(cls, plan_id: int) -> None:
        """This Method creates two transaction with types `extend_out` and `unstake`. These
            Transactions present Total value of unstaked and extneded amounts
            of their Plans.
        """
        from exchange.staking.models import StakingTransaction

        plan = cls.get_plan_to_update(plan_id)
        # Make sure plan has been ended.
        if plan.staked_at + plan.staking_period > ir_now():
            raise errors.TooSoon(f'Should Not extend plan #{plan_id} which has not been ended yet.')

        # Make sure no user is `stake` state
        if Plan.get_plan_user_ids_of_users_with_staked_assets(plan_id):
            raise errors.TooSoon(f'Cant extend plan #{plan_id} which has a user in stake state.')

        if plan.transactions.filter(tp=PlanTransaction.TYPES.unstake).exists():
            raise errors.AlreadyCreated(f'Should not re extend plan #{plan_id}.')

        unstaked_amount = StakingTransaction.objects.filter(
            plan_id=plan_id,
            child=None,
            tp=StakingTransaction.TYPES.unstake,
        ).aggregate(total=models.Sum('amount')).get('total') or Decimal('0')

        extended_amount = StakingTransaction.objects.filter(
            plan_id=plan_id,
            child=None,
            tp=StakingTransaction.TYPES.extend_out,
        ).aggregate(total=models.Sum('amount')).get('total') or Decimal('0')
        plan.extended_capacity = extended_amount
        plan.save(update_fields=('extended_capacity',))
        plan_stake_transaction = plan.get_active_transaction_by_tp(PlanTransaction.TYPES.stake)
        PlanTransaction.objects.create(
            plan=plan,
            parent=plan_stake_transaction,
            tp=PlanTransaction.TYPES.extend_out,
            amount=extended_amount,
        )
        PlanTransaction.objects.create(
            plan=plan,
            parent=plan_stake_transaction,
            tp=PlanTransaction.TYPES.unstake,
            amount=unstaked_amount,
        )


    @classmethod
    @transaction.atomic
    def approve_reward_amount(cls, plan_id: int):
        """Marking admin approved plan (to create alerts in admin panel)"""
        plan = cls.get_plan_to_update(plan_id)
        try:
            latest_announcement = plan.get_active_transaction_by_tp(PlanTransaction.TYPES.announce_reward)
        except PlanTransaction.DoesNotExist as e:
            if plan.transactions.filter(tp=PlanTransaction.TYPES.admin_reward_approved).exists():
                raise errors.AlreadyCreated(f'Plan #{plan_id} already has been approved.') from e
            raise errors.ParentIsNotCreated(f'Cant approve plan #{plan_id} reward which has no announced reward.') from e

        # Ensure the last created announcement is really last announcement
        if latest_announcement.created_at < plan.staked_at + plan.staking_period:
            raise errors.TooSoon(f'It is Too soon to approve Plan #{plan_id} amount.')

        PlanTransaction.objects.create(
            plan=plan,
            tp=PlanTransaction.TYPES.admin_reward_approved,
            amount=latest_announcement.amount,
            created_at=(
                plan.staked_at + plan.staking_period
            ),  # `Officially` we pay user rewards at the end of staking
        )

    @classmethod
    @transaction.atomic
    def withdraw_users_reward_from_plan(cls, plan_id: int):
        """Note that last announced reward amount being used as users received amount,
            calling this method by admin will initiate paying rewards to users.
        """
        plan = cls.get_plan_to_update(plan_id)
        try:
            latest_announcement = plan.get_active_transaction_by_tp(PlanTransaction.TYPES.announce_reward)
        except PlanTransaction.DoesNotExist as e:
            if plan.transactions.filter(tp=PlanTransaction.TYPES.give_reward).exists():
                raise errors.AlreadyCreated(
                    f'Reward of plan #{plan_id} has already been withdraw from staking system user wallet.',
                ) from e
            raise errors.ParentIsNotCreated(
                f'Cant give reward of plan #{plan_id} where there is no active reward announcement.',
            ) from e

        # Ensure the last created announcement is really last announcement
        if latest_announcement.created_at < plan.staked_at + plan.staking_period:
            raise errors.TooSoon(
                f'Cant give rewards of plan #{plan_id} when last reward has not been announced yet.',
            )

        # Create Staking Fee Transaction
        fee_amount = (latest_announcement.amount * (
            plan.fee / (1 - plan.fee)
        )).quantize(Decimal('1E-10'), ROUND_DOWN)

        for user, amount in (
            (get_fee_collector_user(), fee_amount),
            (get_asset_collector_user(), -fee_amount),
        ):
            fee_transaction = PlanTransaction.objects.create(
                plan=plan,
                tp=PlanTransaction.TYPES.fee,
                amount=amount,
            )
            try:
                wallet_transaction = create_and_commit_transaction(
                    user_id=user.id,
                    currency=plan.currency,
                    amount=amount,
                    ref_id=fee_transaction.id,
                    ref_module=RefMod.staking_fee,
                    description=f'reward fee, planId: {plan.id}',
                )
            except ValueError as e:
                raise errors.FailedAssetTransfer(
                    f'system user done have enough assets to withdraw reward fee of plan #{plan.id}.',
                ) from e

            fee_transaction.wallet_transaction = wallet_transaction
            fee_transaction.save(update_fields=('wallet_transaction',))

        users_reward_amount = (plan.filled_capacity / plan.total_capacity) * latest_announcement.amount
        # Create Plan users total rewards transaction
        reward_transaction = PlanTransaction.objects.create(
            plan=plan,
            tp=PlanTransaction.TYPES.give_reward,
            amount=users_reward_amount,
            created_at=(
                plan.staked_at + plan.staking_period
            ),  # `Officially` we pay user rewards at the end of staking
            parent=latest_announcement,  # Deactivate latest_announcement transaction
        )
        try:
            wallet_transaction = create_and_commit_transaction(
                user_id=get_asset_collector_user().id,
                currency=plan.currency,
                amount=Decimal('-1') * users_reward_amount,
                ref_id=reward_transaction.id,
                ref_module=RefMod.staking_reward,
                description=f'rewards withdrawn to be paid to users, planId: {plan.id}',
            )
        except ValueError as e:
            raise errors.FailedAssetTransfer(
                f'system user done have enough assets to withdraw users rewards of plan #{plan.id}.',
            ) from e

        reward_transaction.wallet_transaction = wallet_transaction
        reward_transaction.save(update_fields=('wallet_transaction',))

        system_reward_amount = latest_announcement.amount - users_reward_amount
        for user, amount in (
            (get_nobitex_reward_collector(), system_reward_amount),
            (get_asset_collector_user(), -system_reward_amount),
        ):
            plan_transaction = PlanTransaction.objects.create(
                plan=plan,
                tp=PlanTransaction.TYPES.system_reward,
                amount=amount,
            )
            if system_reward_amount:
                try:
                    wallet_transaction = create_and_commit_transaction(
                        user_id=user.id,
                        currency=plan.currency,
                        amount=amount,
                        ref_id=plan_transaction.id,
                        ref_module=RefMod.staking_reward,
                        description=f'system rewards for unfilled capacity, planId: {plan.id}',
                    )
                except ValueError as e:
                    raise errors.FailedAssetTransfer(
                        f'system user done have enough assets to withdraw unfilled capacity rewards of plan #{plan.id}.',
                    ) from e

                plan_transaction.wallet_transaction = wallet_transaction
                plan_transaction.save(update_fields=('wallet_transaction',))

    def get_extension(self):
        try:
            return Plan.objects.select_for_update().get(extended_from_id=self.id)
        except (Plan.DoesNotExist, MultipleObjectsReturned) as e:
            raise errors.AdminMistake(f'Cant Get ExtensionPlan of #{self.id}') from e

    @classmethod
    @transaction.atomic
    def create_extend_in_transaction(cls, plan_id: int) -> None:
        """This method will transfer staked assets of plan with pk `plan_id` to its
            extension.
        """
        plan = Plan.get_plan_to_update(plan_id)

        if not plan.is_extendable:
            raise errors.NonExtendablePlan(f'Cant extend non extendable plan #{plan_id}')

        try:
            parent_transaction = plan.get_active_transaction_by_tp(PlanTransaction.TYPES.extend_out)
        except PlanTransaction.DoesNotExist as e:
            if PlanTransaction.objects.filter(tp=PlanTransaction.TYPES.extend_in, plan__extended_from=plan).exists():
                raise errors.AlreadyCreated(f'Extending stakings of plan #{plan_id} has already been done.') from e
            raise errors.ParentIsNotCreated(
                f'Cant extend stakings of plan #{plan_id} to its extension when `extend_out` transaction has'
                + 'not been created for plan #{plan_id}.',
            ) from e

        extension_plan = plan.get_extension()

        PlanTransaction.objects.create(
            plan=extension_plan,
            parent=parent_transaction,
            tp=PlanTransaction.TYPES.extend_in,
            amount=parent_transaction.amount,
        )

        extension_plan.add_to_stake_amount(parent_transaction.amount)
        extension_plan.total_capacity += parent_transaction.amount
        extension_plan.filled_by_extension += parent_transaction.amount
        extension_plan.filled_capacity += parent_transaction.amount
        extension_plan.save(update_fields=('total_capacity', 'filled_by_extension', 'filled_capacity'))

    @classmethod
    @transaction.atomic
    def stake_assets(cls, plan_id: int) -> None:
        plan = cls.get_plan_to_update(plan_id)
        if ir_now() < plan.staked_at:
            raise errors.TooSoon(f'It is too soon to stake plan #{plan_id} assets.')

        approval_transaction = plan.transactions.filter(
            tp=PlanTransaction.TYPES.system_stake_amount_approval, child=None,
        ).first()

        if approval_transaction is None:
            if plan.transactions.filter(tp=PlanTransaction.TYPES.system_stake_amount_approval).exists():
                raise errors.AlreadyCreated(f'There is no stake amount approval of plan #{plan_id}.')
            raise errors.ParentIsNotCreated(f'Plan #{plan_id} assets has already been staked.')

        cls.deactivate_transaction(approval_transaction)
        plan.add_to_stake_amount(approval_transaction.amount)

    @classmethod
    def deactivate_transaction(cls, plan_transaction):
        PlanTransaction.objects.create(
            tp=PlanTransaction.TYPES.deactivator,
            parent=plan_transaction,
            plan_id=plan_transaction.plan_id,
        )

    def add_to_stake_amount(self, amount: Decimal) -> None:
        try:
            create_transaction = self.get_active_transaction_by_tp(PlanTransaction.TYPES.stake)
            create_transaction.amount += amount
            create_transaction.save(update_fields=('amount',))
        except PlanTransaction.DoesNotExist:
            self.transactions.create(
                tp=PlanTransaction.TYPES.stake,
                amount=amount,
            )

    @classmethod
    @transaction.atomic
    def create_release_transaction(cls, plan_id: int) -> None:
        plan = cls.get_plan_to_update(plan_id)

        # Assert release time has arrived
        if ir_now() < plan.staked_at + plan.staking_period + plan.unstaking_period:
            raise errors.TooSoon(f'It is too soon to release assets of plan #{plan_id}.')

        try:
            unstake_transaction = plan.get_active_transaction_by_tp(PlanTransaction.TYPES.unstake)
        except PlanTransaction.DoesNotExist as e:
            if plan.transactions.filter(tp=PlanTransaction.TYPES.release).exists():
                raise errors.AlreadyCreated(
                    f'Releasing assets of plan #{plan_id} has already been withdrawn from system user.',
                ) from e
            raise errors.ParentIsNotCreated(
                f'Cant create `release` transaction for plan #{plan_id} where there is no `unstake` transaction.',
            ) from e

        release_transaction = PlanTransaction.objects.create(
            plan=plan,
            tp=PlanTransaction.TYPES.release,
            parent=unstake_transaction,
            amount=unstake_transaction.amount,
        )
        plan.released_capacity = unstake_transaction.amount
        plan.save(update_fields=('released_capacity',))
        if unstake_transaction.amount:
            try:
                wallet_transaction = create_and_commit_transaction(
                    user_id=get_asset_collector_user().id,
                    currency=plan.currency,
                    amount=-unstake_transaction.amount,
                    ref_id=release_transaction.id,
                    ref_module=RefMod.staking_release,
                    description=f'release user assets (planId: {plan.id})',
                )
            except ValueError as e:
                raise errors.FailedAssetTransfer(
                    f'Not enough assets to release users assets of plan #{plan.id}.',
                ) from e

            release_transaction.wallet_transaction = wallet_transaction
            release_transaction.save(update_fields=('wallet_transaction',))


    @staticmethod
    @measure_time(metric=Metrics.PLANS_TO_STAKE_QUERY_TIME)
    def get_plan_ids_to_stake() -> List[int]:
        """return id of plans with admin or system approved, or extended stake amount, that
        stake transaction should be created for them.
        """
        return list(
            Plan.objects.filter(
                transaction__tp=PlanTransaction.TYPES.system_stake_amount_approval,
                transaction__child=None,
                staked_at__lt=ir_now(),
            )
            .values_list('id', flat=True)
            .distinct()
        )

    @staticmethod
    def get_plan_user_ids(plan_id: int) -> 'models.QuerySet[int]':
        from exchange.staking.models import StakingTransaction

        return (
            StakingTransaction.objects.filter(plan_id=plan_id)
            .order_by('user_id')
            .values_list('user_id', flat=True)
            .distinct()
        )

    @classmethod
    def get_user_ids_to_extend(cls, plan_id: int) -> 'models.QuerySet[int]':
        from exchange.staking.models import StakingTransaction

        return (
            StakingTransaction.objects.filter(
                plan_id=plan_id,
                tp=StakingTransaction.TYPES.extend_out,
                child=None,
            )
            .values_list('user_id', flat=True)
            .order_by('user_id')
            .distinct()
        )

    @staticmethod
    def get_plan_user_ids_of_users_with_staked_assets(plan_id: int) -> 'models.QuerySet[int]':
        from exchange.staking.models import StakingTransaction

        return StakingTransaction.objects.filter(
            plan_id=plan_id, tp=StakingTransaction.TYPES.stake, child=None,
        ).values_list('user_id', flat=True).distinct()

    @staticmethod
    def get_plan_user_ids_of_users_with_unreleased_assets(plan_id: int):
        from exchange.staking.models import StakingTransaction

        return StakingTransaction.objects.filter(
            plan_id=plan_id, tp=StakingTransaction.TYPES.unstake, child=None,
        ).values_list('user_id', flat=True).distinct()

    @staticmethod
    def get_plan_user_ids_to_pay_reward(plan_id: int):
        from exchange.staking.models import StakingTransaction

        return (
            StakingTransaction.objects.filter(
                plan_id=plan_id,
                tp=StakingTransaction.TYPES.stake,
                amount__gt=0,
            )
            .exclude(
                user_id__in=StakingTransaction.objects.filter(
                    plan_id=plan_id,
                    tp=StakingTransaction.TYPES.give_reward,
                ).values_list('user_id', flat=True)
            )
            .values_list('user_id', flat=True)
            .distinct()
        )

    @staticmethod
    @measure_time(metric=Metrics.PLANS_TO_ASSIGN_STAKING_TO_USERS_QUERY_TIME)
    def get_plan_ids_to_assign_staking_to_users() -> List[int]:
        return list(Plan.objects.filter(
            transaction__tp=PlanTransaction.TYPES.stake,
            transaction__amount__gt=0,
        ).values_list('id', flat=True).distinct())

    @staticmethod
    @measure_time(metric=Metrics.PLANS_TO_END_ITS_USER_STAKING_QUERY_TIME)
    def get_plan_ids_to_end_its_user_staking() -> List[int]:
        """This method return list of plan id with following conditions:
            1. staking period of plan has passed.
            2. there users who have staking with `stake` state in this plan.
        """
        return list(
            Plan.objects.filter(
                staked_at__lt=ir_now() - F('staking_period'),
                staking_transaction__tp=PlanTransaction.TYPES.stake,
                staking_transaction__child=None,
            )
            .values_list('id', flat=True)
            .distinct(),
        )

    @staticmethod
    @measure_time(metric=Metrics.PLANS_TO_CREATE_RELEASE_TRANSACTION_QUERY_TIME)
    def get_plan_ids_to_create_release_transaction() -> List[int]:
        return list(
            Plan.objects.filter(
                staked_at__lt=ir_now() - F('staking_period') - F('unstaking_period'),
                transaction__tp=PlanTransaction.TYPES.unstake,
                transaction__child=None,
            )
            .values_list('id', flat=True)
            .distinct(),
        )

    @staticmethod
    @measure_time(metric=Metrics.PLANS_TO_RELEASE_ITS_USER_ASSETS_QUERY_TIME)
    def get_plan_ids_to_release_its_user_assets() -> List[int]:
        from exchange.staking.models import StakingTransaction

        return list(
            Plan.objects.filter(
                staking_transaction__tp=StakingTransaction.TYPES.unstake,
                staking_transaction__child=None,
            )
            .values_list('id', flat=True)
            .distinct(),
        )

    @staticmethod
    def get_user_ids_to_release_assets(plan_id: int) -> 'models.QuerySet[int]':
        from exchange.staking.models import StakingTransaction

        return (
            StakingTransaction.objects.filter(
                plan_id=plan_id,
                tp=PlanTransaction.TYPES.unstake,
                child=None,
            )
            .values_list('user_id', flat=True)
            .distinct()
        )

    @staticmethod
    @measure_time(metric=Metrics.PLANS_TO_APPROVE_STAKE_AMOUNT_QUERY_TIME)
    def get_plan_ids_to_approve_stake_amount() -> List[int]:
        return list(
            Plan.objects.filter(opened_at__lt=ir_now() - F('request_period'))
            .exclude(transaction__tp=PlanTransaction.TYPES.system_stake_amount_approval)
            .values_list('id', flat=True),
        )

    @staticmethod
    @measure_time(metric=Metrics.PLANS_TO_FETCH_REWARDS_QUERY_TIME)
    def get_plan_ids_to_fetch_rewards() -> List[int]:
        return list(
            Plan.objects.filter(
                staked_at__lt=ir_now(),
                staked_at__gt=ir_now() - F('staking_period') - F('reward_announcement_period'),
            )
            .exclude(
                id__in=Plan.objects.filter(
                    transaction__tp=PlanTransaction.TYPES.fetched_reward,
                    transaction__created_at__gt=ir_now() - timedelta(hours=1),
                )
                .values_list('id', flat=True)
                .distinct(),
            )
            .values_list('id', flat=True),
        )

    @staticmethod
    @measure_time(metric=Metrics.PLANS_TO_ANNOUNCE_REWARDS_QUERY_TIME)
    def get_plan_ids_to_announce_rewards() -> List[int]:
        return list(
            Plan.objects.filter(staked_at__lt=ir_now())
            .exclude(
                pk__in=Plan.objects.filter(
                    Q(transaction__created_at__gt=ir_now() - F('reward_announcement_period'))
                    | Q(transaction__created_at=F('staked_at') + F('staking_period')),
                    transaction__tp=PlanTransaction.TYPES.announce_reward,
                )
                .values_list('id', flat=True)
                .distinct(),
            )
            .values_list('id', flat=True),
        )

    @staticmethod
    @measure_time(metric=Metrics.PLANS_TO_PAY_REWARDS_QUERY_TIME)
    def get_plan_ids_to_pay_rewards() -> List[int]:
        return list(Plan.objects.filter(
            transaction__tp=PlanTransaction.TYPES.give_reward,
            transaction__amount__gt=0,
        ).values_list('id', flat=True))

    @staticmethod
    @measure_time(metric=Metrics.PLANS_TO_EXTEND_STAKING_QUERY_TIME)
    def get_plan_ids_to_extend_staking() -> List[int]:
        return list(Plan.objects.filter(
            is_extendable=True,
            transaction__tp=PlanTransaction.TYPES.extend_out,
            transaction__child=None,
        ).values_list('id', flat=True).distinct())

    @staticmethod
    @measure_time(metric=Metrics.PLANS_TO_CREATE_EXTEND_OUT_TRANSACTION_QUERY_TIME)
    def get_plan_ids_create_extend_out_transaction() -> List[int]:
        return list(
            Plan.objects.filter(
                staked_at__lt=ir_now() - F('staking_period'),
                transaction__tp=PlanTransaction.TYPES.stake,
                transaction__child=None,
            )
            .values_list('id', flat=True)
            .distinct(),
        )

    @staticmethod
    @measure_time(metric=Metrics.PLANS_TO_EXTEND_USERS_ASSETS_QUERY_TIME)
    def get_plan_ids_to_extend_users_assets() -> List[int]:
        return list(
            Plan.objects.filter(
                staking_transaction__tp=PlanTransaction.TYPES.extend_out,
                staking_transaction__child=None,
            )
            .exclude(
                pk__in=Plan.objects.filter(
                    transaction__tp=PlanTransaction.TYPES.extend_out,
                    transaction__child=None,
                )
            )
            .values_list('id', flat=True)
            .distinct()
        )

    @staticmethod
    @measure_time(metric=Metrics.USERS_TO_APPLY_END_REQUESTS_QUERY_TIME)
    def get_user_ids_to_apply_instant_end_requests(plan_id: int) -> List[int]:
        from exchange.staking.models import StakingTransaction

        return list(
            StakingTransaction.objects.filter(
                plan_id=plan_id,
                tp=StakingTransaction.TYPES.instant_end_request,
                child=None,
            )
            .values_list('user_id', flat=True)
            .distinct(),
        )

    @staticmethod
    def get_open_plan_ids() -> 'models.QuerySet[int]':
        return Plan.objects.filter(
            opened_at__lt=ir_now(),
            opened_at__gt=ir_now() - F('request_period'),
            total_capacity__gt=F('filled_capacity') + F('min_staking_amount'),
        ).values_list('id', flat=True)

    @property
    def ancestor_plans(self) -> List['Plan']:
        similar_platform_plans = (
            self.all_plans()
            .filter(external_platform_id=self.external_platform_id, staking_period=self.staking_period)
            .only('extended_from')
            .in_bulk()
        )
        ancestor_plans = []
        parent_plan = self
        while parent_plan:
            ancestor_plans.append(parent_plan)
            parent_plan = similar_platform_plans.get(parent_plan.extended_from_id)
        return ancestor_plans


# Defined externally to be used in PlanTransaction.Meta.constraints
_PlanTransactionTypes = Choices(
    (403, 'system_stake_amount_approval', 'system_stake_amount_approval'),
    (404, 'un_applied_instant_unstake_requests', 'un_applied_instant_unstake_requests'),  # Deprecated
    (301, 'announce_reward', 'announce_reward'),
    (302, 'give_reward', 'give_reward'),
    (401, 'admin_reward_approved', 'admin_reward_approved'),
    (322, 'system_reward', 'system_reward'),
    (303, 'stake', 'stake'),
    (304, 'release', 'release'),
    (305, 'unstake', 'unstake'),
    (306, 'instant_unstake_requests', 'instant_unstake_requests'),
    (311, 'extend_out', 'extend_out'),
    (312, 'extend_in', 'extend_in'),
    (313, 'fee', 'fee'),
    (314, 'fetched_reward', 'fetched_reward'),
    (999, 'deactivator', 'deactivator'),
)


class PlanTransaction(models.Model):
    TYPES = _PlanTransactionTypes

    plan = models.ForeignKey(
        Plan, related_name='transactions', related_query_name='transaction', on_delete=models.CASCADE,
    )
    parent = models.ForeignKey(
        'self', null=True, default=None, related_name='children', related_query_name='child', on_delete=models.CASCADE,
    )
    tp = models.SmallIntegerField(choices=TYPES)
    amount = models.DecimalField(max_digits=30, decimal_places=10, default=0)
    created_at = models.DateTimeField(default=ir_now)
    wallet_transaction = models.ForeignKey(
        Transaction, related_name='+', null=True, default=None, on_delete=models.CASCADE,
    )

    class Meta:
        indexes = (
            models.Index(
                fields=('tp',),
                name='staking_plantransaction_tp_idx',
            ),
        )


class UserWatch(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)

    class Meta:
        unique_together = (('user', 'plan'),)

    @classmethod
    def get(cls, user_id) -> 'models.QuerySet[int]':
        return cls.objects.filter(user_id=user_id).values_list('plan_id', flat=True)

    @classmethod
    def add(cls, user_id, plan_id) -> None:
        Plan.check_existence(plan_id)
        cls.objects.get_or_create(user_id=user_id, plan_id=plan_id)

    @classmethod
    def remove(cls, user_id, plan_id) -> None:
        Plan.check_existence(plan_id)
        cls.objects.filter(user_id=user_id, plan_id=plan_id).delete()

    @classmethod
    def clean_up(cls):
        """Removing Items related to started Plans"""
        cls.objects.filter(plan__staked_at__lt=ir_now() - F('plan__staking_period')).delete()

    @classmethod
    @measure_time_cm(metric=str(Metrics.NOTIFICATION_USER_WATCH_PLAN_CAPACITY_INCREASE_TIME))
    def notify_users(cls, plan_id) -> None:
        from exchange.staking.notifier import Notifier, StakingNotifTopic
        plan = Plan.objects.get(pk=plan_id)
        try:
            plan.check_if_plan_is_open_to_accepting_requests()
        except errors.TooLate:
            return

        currency = plan.currency
        user_ids = list(cls.objects.filter(plan_id=plan_id).values_list('user_id', flat=True))
        sent_ids = []
        for user_id in user_ids:
            try:
                Notifier.notify(
                    StakingNotifTopic.PLAN_CAPACITY_INCREASE,
                    user_id,
                    {
                        'currency': currency,
                        'platform': plan.external_platform.type_fa_display,
                        'platform_code': ExternalEarningPlatform.get_type_machine_display(plan.external_platform.tp),
                    },
                )
                sent_ids.append(user_id)
            except Exception:  # pylint: disable=broad-except
                report_exception()

        UserWatch.objects.filter(plan_id=plan_id, user_id__in=sent_ids).delete()

    @classmethod
    def extend_watches(cls):
        extended_watch_plans = (
            cls.objects.filter(
                plan__is_extendable=True,
                plan__staked_at__lt=ir_now(),
                plan__extended_to__isnull=False,
            )
            .values_list('plan_id', 'plan__extended_to')
            .distinct()
        )
        for plan_id, extended_to_plan_id in extended_watch_plans:
            already_extended_users = cls.objects.filter(plan_id=extended_to_plan_id).values_list('user_id', flat=True)
            cls.objects.filter(plan_id=plan_id).exclude(
                user_id__in=already_extended_users,
            ).update(plan_id=extended_to_plan_id)
            cls.objects.filter(user_id__in=already_extended_users, plan_id=plan_id).delete()

