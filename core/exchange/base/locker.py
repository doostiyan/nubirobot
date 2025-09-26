"""DB Locking Utilities"""
from django.db import connection
from model_utils.choices import Choices

from exchange.base.helpers import deterministic_hash


class Locker:
    WITHDRAW_VERIFICATION = 'withdraw_verification'
    LOCKS = Choices(
        (1, 'user', 'User'),
        (2, 'wallet', 'Wallet'),
        (3, 'market', 'Market'),
        (4, 'order', 'Order'),
        (5, 'xchange', 'Xchange'),
        (6, WITHDRAW_VERIFICATION, 'Withdraw Verification'),
        (7, 'socialtrade', 'SocialTrade'),
    )

    @classmethod
    def require_lock(cls, lock_type, lock_id, shared=False):
        """Get an exclusive PostgreSQL transaction-level advisory lock."""
        lock_type = getattr(cls.LOCKS, lock_type, deterministic_hash(lock_type) % 2**30)
        lock_function = 'pg_advisory_xact_lock_shared' if shared else 'pg_advisory_xact_lock'
        with connection.cursor() as cursor:
            cursor.execute(
                f'SELECT {lock_function}(%s, %s)',
                [lock_type, lock_id],
            )
