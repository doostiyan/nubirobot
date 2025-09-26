from uuid import UUID

from django.db import models
from model_utils import Choices

from exchange.asset_backed_credit.exceptions import UserNotFoundError
from exchange.asset_backed_credit.metrics import Metrics
from exchange.base.decorators import measure_time
from exchange.base.locker import Locker
from exchange.base.validators import validate_transaction_is_atomic


class InternalUser(models.Model):
    USER_TYPES = Choices(
        (0, 'normal', 'Normal'),  # No email
        (10, 'inactive', 'Inactive'),  # Deprecated
        (20, 'suspicious', 'Suspicious'),  # Deprecated
        (30, 'blocked', 'Blocked'),  # Deprecated
        (40, 'level0', 'Level0'),  # Without KYC
        (42, 'level1p', 'Level1P'),  # Deprecated
        (44, 'level1', 'Level1'),  # Level1
        (45, 'trader', 'Trader'),  # Deprecated, ended on 1402-09-05
        (46, 'level2', 'Level2'),  # Level2
        (90, 'verified', 'Level3'),  # Level3
        (91, 'active', 'Active'),  # Deprecated
        (92, 'trusted', 'Trusted'),  # Level4
        (99, 'nobitex', 'Nobitex'),  # Nobitex Team
        (100, 'system', 'System'),  # System Users
        (101, 'bot', 'Bot'),  # Internal Market Making
        (102, 'staff', 'Staff'),  # Deprecated, use nobitex
    )

    class GenderChoices(models.IntegerChoices):
        UNKNOWN = 0
        MALE = 1
        FEMALE = 2

    uid = models.UUIDField(unique=True, editable=False, null=False, blank=False, db_index=True)
    user_type = models.IntegerField(choices=USER_TYPES, null=True, blank=True)
    national_code = models.CharField(max_length=12, null=True, blank=True)
    mobile = models.CharField(max_length=12, null=True, blank=True, db_index=True)
    email = models.EmailField(blank=True, null=True, unique=True, default=None)

    email_confirmed = models.BooleanField(default=False)
    mobile_confirmed = models.BooleanField(default=False)
    identity_confirmed = models.BooleanField(default=False)
    mobile_identity_confirmed = models.BooleanField(default=False)

    gender = models.IntegerField(choices=GenderChoices.choices, default=GenderChoices.UNKNOWN)
    birthdate_shamsi = models.CharField(max_length=10, null=True, blank=True)
    father_name = models.CharField(max_length=50, null=True, blank=True)
    requires_2fa = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def create(cls, uid: UUID, **kwargs) -> 'InternalUser':
        if not uid:
            raise UserNotFoundError('uid not found')
        return InternalUser.objects.get_or_create(uid=uid, defaults=kwargs)[0]

    @staticmethod
    @measure_time(metric=Metrics.USER_LOCK_WAIT_TIME)
    def get_lock(user_id: int) -> None:
        validate_transaction_is_atomic()
        Locker.require_lock('abc_user_operation', user_id)

    @property
    def is_verified_level_1(self):
        return self.user_type in [
            self.USER_TYPES.level1,
            self.USER_TYPES.level2,
            self.USER_TYPES.verified,
            self.USER_TYPES.trusted,
            self.USER_TYPES.nobitex,
            self.USER_TYPES.staff,
        ]
