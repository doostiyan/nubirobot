import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import connection, models, transaction
from django.db.models import F, JSONField, Q, QuerySet
from django_redis import get_redis_connection
from model_utils import Choices
from pydantic import BaseModel

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import TransactionInsufficientBalanceError, TransactionInvalidError
from exchange.asset_backed_credit.models.user import InternalUser
from exchange.base.calendar import ir_now
from exchange.base.constants import MAX_PRECISION, MONETARY_DECIMAL_PLACES
from exchange.base.logging import report_event
from exchange.base.models import Currencies
from exchange.base.validators import validate_transaction_is_atomic
from exchange.wallet.constants import BALANCE_MAX_DIGITS, TRANSACTION_MAX_DIGITS


class Wallet(models.Model):
    class WalletType(models.IntegerChoices):
        SYSTEM = 0
        COLLATERAL = 10
        DEBIT = 20

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    internal_user = models.ForeignKey(
        InternalUser, related_name='wallets', on_delete=models.CASCADE, null=True, blank=True
    )
    currency = models.IntegerField(choices=Currencies)
    type = models.SmallIntegerField(choices=WalletType.choices)
    balance = models.DecimalField(max_digits=BALANCE_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=0)
    """
    blocked balance will be used to block a specific amount to use for isolated collaterals
    """
    blocked_balance = models.DecimalField(
        max_digits=BALANCE_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=0
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = (models.UniqueConstraint(fields=('user', 'currency', 'type'), name='unique_wallet'),)

    @property
    def is_rial(self) -> bool:
        return self.currency == Currencies.rls

    @property
    def is_tether(self) -> bool:
        return self.currency == Currencies.usdt

    @property
    def available_balance(self) -> Decimal:
        return self.balance - self.blocked_balance

    def create_transaction(
        self,
        tp=None,
        amount: Decimal = None,
        description: str = '',
        created_at: datetime = None,
        ref_module: int = None,
        ref_id: int = None,
        allow_negative_balance=False,
    ) -> Optional['Transaction']:
        if not self.is_active:
            return None
        amount = amount.quantize(MAX_PRECISION)
        balance_after_tx = self.balance + amount
        if not allow_negative_balance and not balance_after_tx >= 0:
            print('[Warning] Not allowing transaction: amount={} > balance={}'.format(amount, self.balance))
            return None
        return Transaction(
            wallet=self,
            type=tp,
            amount=amount,
            description=description,
            created_at=created_at or ir_now(),
            ref_module=ref_module,
            ref_id=ref_id,
            balance=balance_after_tx,
        )

    @classmethod
    def get_service_types(cls, wallet_type: int) -> List[int]:
        from exchange.asset_backed_credit.models import Service  # due to circular import

        if wallet_type == cls.WalletType.DEBIT:
            return [Service.TYPES.debit]

        return [Service.TYPES.credit, Service.TYPES.loan]


class Transaction(models.Model):
    class Type(models.IntegerChoices):
        TRANSFER = 10
        BUY = 20
        SELL = 30
        SETTLEMENT = 40

    class RefModule(models.IntegerChoices):
        TRANSFER = 0
        SETTLEMENT_USER = 10
        SETTLEMENT_PROVIDER = 20
        SETTLEMENT_INSURANCE = 30

    wallet = models.ForeignKey(Wallet, related_name='transactions', on_delete=models.CASCADE)
    type = models.SmallIntegerField(choices=Type.choices)
    amount = models.DecimalField(max_digits=TRANSACTION_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES)
    balance = models.DecimalField(
        max_digits=BALANCE_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField()
    description = models.TextField()
    ref_module = models.SmallIntegerField(choices=RefModule.choices, null=True, blank=True)
    ref_id = models.BigIntegerField(null=True, blank=True)
    batch_id = models.UUIDField(null=True, blank=True)

    @dataclass
    class Ref:
        ref_module: int
        ref_id: int

    class Meta:
        constraints = (models.UniqueConstraint(fields=('ref_module', 'ref_id'), name='unique_ref'),)

    @property
    def currency(self) -> int:
        return self.wallet.currency

    def commit(self, ref: 'Ref' = None, allow_negative_balance=False):
        """Save the transaction to DB, updating wallet's balance."""
        self.set_ref(ref)

        validate_transaction_is_atomic()

        if not self._check_transaction():
            raise TransactionInvalidError

        with transaction.atomic(savepoint=not connection.in_atomic_block):
            updated_balance = self._update_wallet_balance()

            # Safe-guard check to prevent over spending
            if updated_balance < Decimal('0') and not allow_negative_balance:
                report_event(message='Negative balance', level='error')
                raise TransactionInsufficientBalanceError('Balance Error In Commiting Transaction')

            self.wallet.balance = self.balance = updated_balance
            self.save()

    def set_ref(self, ref: 'Ref') -> None:
        if ref is None:
            return

        self.ref_module = ref.ref_module
        self.ref_id = ref.ref_id

    def _check_transaction(self) -> bool:
        if not all([self.type, self.amount is not None, self.wallet, self.created_at]):
            return False
        if not self.wallet.is_active:
            return False
        return True

    def _update_wallet_balance(self) -> Decimal:
        """
        Update the wallet balance and return the updated balance

        NOTE: We use pure SQL syntax because django ORM doesn't support RETURNING keyword of PostgreSQL
        """
        with connection.cursor() as cursor:
            cursor.execute(
                'UPDATE asset_backed_credit_wallet SET balance = balance + %s WHERE id = %s RETURNING balance',
                [self.amount, self.wallet_id],
            )
            result = cursor.fetchone()
        return result[0]


class WalletCache(BaseModel):
    id: Optional[int] = None
    currency: int
    type: int
    balance: Decimal
    blocked_balance: Decimal
    updated_at: Decimal


class WalletCacheManager:
    """
    Manager for caching wallet information per user in Redis.
    """

    def __init__(self, client=None):
        self._client = client

    @staticmethod
    def _user_wallets_key(user_id: uuid.UUID) -> str:
        return f'abc:wallet_cache:{user_id}'

    @staticmethod
    def _wallet_field(wallet_type: int, currency: int) -> str:
        return f'{wallet_type}:{currency}'

    def get_client(self):
        return self._client or get_redis_connection("default")

    def invalidate(self, user_id: uuid.UUID) -> None:
        """
        Remove all cached wallets for the given user.
        """
        client = self.get_client()
        key = self._user_wallets_key(user_id)
        client.delete(key)

    def get(self, user_id: uuid.UUID, wallet_type: int, currency: int) -> Optional[WalletCache]:
        """
        Retrieve a single cached wallet for a user, wallet_type, and currency.
        """
        client = self.get_client()
        key = self._user_wallets_key(user_id)
        field = self._wallet_field(wallet_type, currency)

        data = client.hget(key, field)
        if not data:
            return None
        return self._parse_wallet_cache(data, key, field)

    @classmethod
    def _parse_wallet_cache(cls, raw_data, key: str, field: str) -> WalletCache:
        try:
            return WalletCache.parse_raw(raw_data)
        except Exception as exc:
            raise ValueError(f"Failed to parse WalletCache for {key}/{field}: {exc}") from exc

    def get_by_user(self, user_id: uuid.UUID) -> List[WalletCache]:
        """
        Fetch all cached wallets for a user.
        """
        client = self.get_client()
        key = self._user_wallets_key(user_id)
        raw_data = client.hgetall(key)
        wallets = []
        for field, value in raw_data.items():
            wallets.append(
                self._parse_wallet_cache(
                    raw_data=value, key=key, field=field.decode() if isinstance(field, bytes) else field
                )
            )
        return wallets

    def get_by_type(self, user_id: uuid.UUID, wallet_type: int) -> List[WalletCache]:
        """
        Fetch all wallets for a user filtered by wallet_type.
        """
        return [wallet for wallet in self.get_by_user(user_id) if wallet.type == wallet_type]

    def get_by_users(self, user_ids: List[uuid.UUID]) -> Dict[uuid.UUID, List[WalletCache]]:
        """
        Fetch all cached wallets for each user in user_ids.
        Returns: { user_id: [WalletCache, ...] }
        """
        client = self.get_client()
        keys = [self._user_wallets_key(uid) for uid in user_ids]
        pipe = client.pipeline()
        for key in keys:
            pipe.hgetall(key)
        raw_results = pipe.execute()

        result: Dict[int, List[WalletCache]] = {}
        for user_id, raw_data in zip(user_ids, raw_results):
            wallets = []
            for field, value in (raw_data or {}).items():
                wallets.append(
                    self._parse_wallet_cache(
                        raw_data=value,
                        key=self._user_wallets_key(user_id),
                        field=field.decode() if isinstance(field, bytes) else field,
                    )
                )
            result[user_id] = wallets
        return result

    def get_by_users_and_type(self, user_ids: List[uuid.UUID], wallet_type: int) -> Dict[uuid.UUID, List[WalletCache]]:
        """
        Fetch all cached wallets for users filtered by wallet_type.
        Returns: { user_id: [WalletCache, ...] }
        """
        all_wallets = self.get_by_users(user_ids)
        return {
            user_id: [wallet for wallet in wallets if wallet.type == wallet_type]
            for user_id, wallets in all_wallets.items()
        }

    def set(self, user_id: uuid.UUID, wallet: WalletCache) -> None:
        """
        Cache a single wallet for a user.
        """
        if wallet is None:
            return

        client = self.get_client()
        key = self._user_wallets_key(user_id)
        field = self._wallet_field(wallet.type, wallet.currency)
        client.hset(key, field, wallet.json())

    def bulk_set(self, user_id: uuid.UUID, wallets: List[WalletCache]) -> None:
        """
        Bulk cache multiple wallets for a user.
        """
        if not wallets:
            return

        client = self.get_client()
        key = self._user_wallets_key(user_id)
        pipe = client.pipeline()
        for wallet in wallets:
            field = self._wallet_field(wallet.type, wallet.currency)
            pipe.hset(key, field, wallet.json())
        pipe.execute()


class WalletTransferLog(models.Model):
    STATUS = Choices(
        (1, 'new', 'New'),
        (2, 'done', 'Done'),
        (3, 'pending_to_retry', 'Pending to Retry'),
        (4, 'failed_permanently', 'Failed Permanently'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    internal_user = models.ForeignKey(InternalUser, on_delete=models.CASCADE, null=True, blank=True)

    status = models.SmallIntegerField(choices=STATUS, default=STATUS.new)
    failed_permanently_reason = models.CharField(max_length=256, blank=True, null=True)
    src_wallet_type = models.SmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)])
    dst_wallet_type = models.SmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)])
    transfer_items = JSONField()

    response_body = JSONField(blank=True, null=True)
    response_code = models.SmallIntegerField(blank=True, null=True)

    api_called_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    idempotency = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, null=False, blank=False)
    retry = models.SmallIntegerField(default=0)
    external_transfer_id = models.BigIntegerField(blank=True, null=True)

    @classmethod
    def create(
        cls,
        user: User,
        internal_user: InternalUser,
        src_wallet_type: int,
        dst_wallet_type: int,
        transfer_items: Dict[int, Decimal],
        status: int = STATUS.new,
        **kwargs,
    ) -> 'WalletTransferLog':
        return cls.objects.create(
            user=user,
            internal_user=internal_user,
            src_wallet_type=src_wallet_type,
            dst_wallet_type=dst_wallet_type,
            transfer_items={currency: str(amount) for currency, amount in transfer_items.items()},
            status=status,
            **kwargs,
        )

    def update_api_data(
        self,
        response_body: dict,
        response_code: int,
        external_transfer_id: Optional[int] = None,
    ) -> 'WalletTransferLog':
        update_fields = ['api_called_at', 'response_body', 'response_code']
        if self.api_called_at:
            self.retry = F("retry") + 1
            update_fields.append('retry')
        if external_transfer_id:
            self.external_transfer_id = external_transfer_id
            update_fields.append('external_transfer_id')

        self.api_called_at = ir_now()
        self.response_body = response_body
        self.response_code = response_code
        self.save(update_fields=update_fields)
        return self

    def update_status(self, new_status: STATUS, failed_permanently_reason: str = None):
        update_fields = ['status']
        self.status = new_status
        if failed_permanently_reason:
            self.failed_permanently_reason = failed_permanently_reason
            update_fields.append('failed_permanently_reason')

        self.save(update_fields=update_fields)

    @classmethod
    def get_pending_transfer_log(cls, transfer_id: int) -> 'WalletTransferLog':
        return cls.objects.select_for_update(no_key=True).get(
            id=transfer_id,
            status__in=[cls.STATUS.new, cls.STATUS.pending_to_retry],
            external_transfer_id__isnull=True,
        )

    @classmethod
    def get_pending_transfer_logs(cls) -> QuerySet['WalletTransferLog']:
        new_logs = Q(
            status=cls.STATUS.new,
            api_called_at__isnull=True,
            created_at__lte=ir_now() - settings.ABC_WITHDRAW_DELAY,
            external_transfer_id__isnull=True,
        )
        retry_logs = Q(
            status=cls.STATUS.pending_to_retry,
            api_called_at__isnull=False,
            external_transfer_id__isnull=True,
        )
        return cls.objects.filter(new_logs | retry_logs)

    @classmethod
    def has_pending_transfer(cls, user: User, src_wallet_type: Optional[int]) -> bool:
        src_wallet_type_q = Q()
        if src_wallet_type is not None:
            src_wallet_type_q = Q(src_wallet_type=src_wallet_type)

        return cls.objects.filter(
            src_wallet_type_q, status__in=[cls.STATUS.new, cls.STATUS.pending_to_retry], user=user
        ).exists()

    def make_none_retryable(self, reason: str = None):
        self.update_status(self.STATUS.failed_permanently, reason)


wallet_cache_manager = WalletCacheManager()
