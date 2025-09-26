from django.db import models

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.staking.models import Plan
from exchange.wallet.models import Transaction


class UserPlan(models.Model):
    class Status(models.IntegerChoices):
        REQUESTED = 10
        ADMIN_REJECTED = 20
        LOCKED = 30  # old staked
        EXTEND_TO_NEXT_CYCLE = 50  # old extend_out
        EXTEND_FROM_PREVIOUS_CYCLE = 60  # old extend_in
        PENDING_RELEASE = 70  # waiting for unstaking period to finish
        RELEASED = 80
        USER_CANCELED = 90

    ALLOW_ADD_SUBSCRIPTION_STATUS = (Status.REQUESTED, Status.EXTEND_FROM_PREVIOUS_CYCLE)
    ALLOW_CHANGE_AUTO_RENEWAL_STATUS = (Status.REQUESTED, Status.LOCKED, Status.EXTEND_FROM_PREVIOUS_CYCLE)

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, related_name='+', on_delete=models.PROTECT)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    next_cycle = models.ForeignKey(to='self', on_delete=models.CASCADE, null=True, blank=True)

    status = models.IntegerField(choices=Status.choices)
    locked_amount = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        help_text='total locked amount',
    )
    requested_amount = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        default=0,
        help_text='total user requested amount',
    )
    admin_rejected_amount = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        default=0,
        help_text='total locked amount rejected by admin',
    )
    admin_reject_reason = models.TextField(blank=True, null=True)
    released_amount = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        default=0,
        help_text='total amount released at the end of cycle',
    )
    extended_to_next_cycle_amount = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        default=0,
        help_text='total amount that is extended to next plan - old extend_out amount',
    )
    extended_from_previous_cycle_amount = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        default=0,
        help_text='total amount that is from previous plan - old extended_in amount',
    )
    early_ended_amount = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        default=0,
        help_text='total amount ended in the lock period - old instant_end amount',
    )
    reward_amount = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        default=0,
        help_text='total gained reward amount',
    )
    auto_renewal = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=ir_now)
    updated_at = models.DateTimeField(auto_now=True)
    locked_at = models.DateTimeField(null=True, blank=True, help_text='the time user plan locked(staked)')
    unlocked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='the time user plan unlocked and pending release - old unstaked and is released after unstaking period',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'user',
                    'plan',
                ],
                name='staking_%(class)s_user_and_plan_unique_constraint',
            )
        ]
        indexes = [
            models.Index(fields=['plan', 'status']),
            models.Index(fields=['plan']),
            models.Index(fields=['user']),
            models.Index(fields=['next_cycle']),
        ]


class UserPlanChangeLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    user_plan = models.ForeignKey(UserPlan, on_delete=models.CASCADE)
    from_status = models.IntegerField(choices=UserPlan.Status.choices, null=True, blank=True)
    to_status = models.IntegerField(choices=UserPlan.Status.choices, null=True, blank=True)
    extra_reason = models.TextField(blank=True, null=True)
    extra_data = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(default=ir_now)
    updated_at = models.DateTimeField(auto_now=True)


class UserPlanRequest(models.Model):
    class Type(models.IntegerChoices):
        SUBSCRIPTION = 10  # old create_request
        EARLY_END = 20  # old instant end and end
        V1_END_REQUEST = 30  # staking v1 end request type
        #  some old deprecated types

    class Status(models.IntegerChoices):
        CREATED = 10
        ADMIN_REJECTED = 20
        FAILED = 30
        USER_CANCELLED = 40
        ACCEPTED = 50
        PENDING_RELEASE = 60  # waiting for unstaking period to finish, used on in v1 end

    id = models.BigAutoField(primary_key=True)
    user_plan = models.ForeignKey(UserPlan, on_delete=models.PROTECT)

    amount = models.DecimalField(max_digits=30, decimal_places=10)
    tp = models.IntegerField(choices=Type.choices)
    status = models.IntegerField(choices=Status.choices)
    failure_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=ir_now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by_admin = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['user_plan']),
            models.Index(fields=['user_plan', 'tp']),
        ]


class UserPlanWalletTransaction(models.Model):
    class Type(models.IntegerChoices):
        REWARD = 10
        SUBSCRIPTION = 20  # old create_request
        RELEASE = 30
        EARLY_END = 40  # old instant end and end

    id = models.BigAutoField(primary_key=True)
    user_plan = models.ForeignKey(UserPlan, on_delete=models.PROTECT)
    wallet_transaction = models.OneToOneField(Transaction, related_name='+', on_delete=models.SET_NULL, null=True)
    user_plan_request = models.ForeignKey(UserPlanRequest, on_delete=models.PROTECT, null=True, blank=True)

    amount = models.DecimalField(max_digits=30, decimal_places=10)
    tp = models.IntegerField(choices=Type.choices)

    class Meta:
        indexes = [
            models.Index(fields=['user_plan']),
            models.Index(fields=['user_plan', 'tp']),
            models.Index(fields=['user_plan_request']),
        ]
