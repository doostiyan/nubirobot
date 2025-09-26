import functools
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import ROUND_DOWN, Decimal, DecimalException
from time import sleep
from typing import Optional, Union

from django.conf import settings
from django.db import connection, models
from django.db import transaction as db_transaction
from django.db.models import Case, Exists, F, OuterRef, Q, QuerySet, Sum, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.functional import cached_property
from model_utils import Choices

from exchange.accounts.constants import SYSTEM_USER_IDS
from exchange.accounts.models import Notification, User
from exchange.accounts.userlevels import UserLevelManager
from exchange.base.api import ParseError
from exchange.base.calendar import get_jalali_first_and_last_of_jalali_month, ir_today
from exchange.base.constants import MONETARY_DECIMAL_PLACES, ZERO
from exchange.base.decorators import cached_method
from exchange.base.emailmanager import EmailManager
from exchange.base.fields import RoundedDecimalField
from exchange.base.formatting import format_money
from exchange.base.logging import report_event, report_exception
from exchange.base.models import AMOUNT_PRECISIONS_V2, DST_CURRENCIES, RIAL, Currencies, Settings, get_currency_codename
from exchange.base.money import money_is_zero, quantize_number
from exchange.base.strings import _t
from exchange.base.validators import validate_transaction_is_atomic
from exchange.market.constants import ORDER_MAX_DIGITS
from exchange.market.marketmanager import MarketManager
from exchange.market.models import Market, Order
from exchange.pool.errors import (
    ConversionOrderException,
    DelegateWhenRevokeInProgressException,
    ExceedCapacityException,
    HighDelegationAmountException,
    InsufficientBalanceException,
    InvalidDelegationAmount,
    LowDelegationAmountException,
    NoAccessException,
    PermissionDeniedException,
)
from exchange.wallet.constants import BALANCE_MAX_DIGITS, TRANSACTION_MAX, TRANSACTION_MAX_DIGITS
from exchange.wallet.estimator import PriceEstimator
from exchange.wallet.models import Transaction, Wallet


class LiquidityPool(models.Model):
    MIN_DELEGATION_SETTING_KEY = 'liquidity_pool_min_delegation_rls'
    MAX_DELEGATION_SETTING_KEY = 'liquidity_pool_max_delegation_rls_%s'

    DEFAULT_MIN_AVAILABLE_RATIO = Decimal('0.1')

    currency = models.SmallIntegerField(choices=Currencies, unique=True, verbose_name='ارز')
    capacity = models.DecimalField(
        max_digits=BALANCE_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, verbose_name='ظرفیت مشارکت'
    )
    filled_capacity = models.DecimalField(
        max_digits=BALANCE_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO, verbose_name='ظرفیت پرشده'
    )
    revoked_capacity = models.DecimalField(
        max_digits=BALANCE_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
        default=ZERO,
        verbose_name="ظرفیت پر نشده‌ی لغو مشارکت",
    )
    manager = models.OneToOneField(User, on_delete=models.PROTECT, related_name='+', verbose_name='مدیر')
    is_active = models.BooleanField(default=False, verbose_name='فعال؟')
    is_private = models.BooleanField(default=False, verbose_name='خصوصی؟')
    current_profit = models.DecimalField(
        max_digits=TRANSACTION_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
        default=ZERO,
        verbose_name='سود دوره فعلی',
    )
    apr = models.DecimalField(max_digits=10, decimal_places=2, null=True, verbose_name='سود تقریبی سالیانه')

    min_available_ratio = models.DecimalField(
        max_digits=2, decimal_places=2, default=DEFAULT_MIN_AVAILABLE_RATIO, verbose_name='نسبت ظرفیت آزاد کمینه'
    )  # Desire: available_balance / capacity > min_available_ratio

    activated_at = models.DateTimeField(blank=True, null=True, verbose_name="تاریخ فعال‌سازی")

    class Meta:
        verbose_name = 'استخر مشارکت'
        verbose_name_plural = 'استخرهای مشارکت'
        constraints = (
            models.CheckConstraint(
                check=Q(
                    filled_capacity__gte=0, filled_capacity__lte=models.F("capacity") + models.F("revoked_capacity")
                ),
                name="pool_capacity_limit",
            ),
        )

    def __str__(self):
        return f'{self.get_currency_display()} Pool'

    @cached_property
    def src_wallet(self) -> Wallet:
        return Wallet.get_user_wallet(self.manager, currency=self.currency)

    def get_dst_wallet(self, dst_currency: int) -> Optional[Wallet]:
        if not hasattr(self, "_dst_wallet_cache"):
            self._dst_wallet_cache = {}
        if dst_currency in self._dst_wallet_cache:
            return self._dst_wallet_cache[dst_currency]
        if self.currency == dst_currency:
            wallet = None
        else:
            wallet = Wallet.get_user_wallet(self.manager, currency=dst_currency)
        self._dst_wallet_cache[dst_currency] = wallet
        return wallet

    @cached_property
    def available_balance(self) -> Decimal:
        return max(self.unblocked_balance - self.revoked_capacity, ZERO)

    @cached_property
    def unblocked_balance(self) -> Decimal:
        from exchange.usermanagement.block import BalanceBlockManager
        in_order = BalanceBlockManager.get_margin_balance_in_order(self.currency)
        if self.currency in DST_CURRENCIES:
            in_order += BalanceBlockManager.get_margin_balance_in_temporal_assessment(self.currency)
        return self.src_wallet.balance - in_order

    @property
    def unfilled_capacity(self) -> Decimal:
        return self.capacity + self.revoked_capacity - self.filled_capacity

    @property
    def min_delegation(self) -> Decimal:
        min_delegation_in_rial = Settings.get_decimal(
            self.MIN_DELEGATION_SETTING_KEY,
            settings.NOBITEX_OPTIONS['liquidityPoolMinDelegationRls'],
        )
        min_amount = self._calc_amount_in_token(min_delegation_in_rial)
        if min_amount is None:
            return self.capacity * Decimal('0.01')
        return min_amount

    def get_max_delegation(self, user_type: int) -> Decimal:
        """Return max delegation amount in the pool's token unit for a user type.
        If max delegation is not set for this type, return first available max delegation for lower types
        If not found, it will return 0.

        Example:
            Setting:
                type 40: unset
                type 45: 100
                type 46: unset
                type 90: 300
                type 91: unset

            Return Value:
                40: 0
                46: 100
                91: 300

        Args:
            user_type (int): User type

        Returns:
            Decimal: max delegation in unit of pool currency
        """
        max_delegation_in_rial = Settings.get_decimal(self.MAX_DELEGATION_SETTING_KEY % user_type, '-1')
        if max_delegation_in_rial == Decimal('-1'):

            if UserLevelManager.is_user_type_eligible_to_delegate_to_liquidity_pool(user_type):
                report_event(
                    f'Liquidity pool max delegation is not set for user type: {user_type}. '
                    f'Fix this by setting {self.MAX_DELEGATION_SETTING_KEY % user_type}'
                )

            fallback_types = [type for type in sorted(User.USER_TYPES._db_values, reverse=True) if type < user_type]
            if (
                len(fallback_types) == 0
                or not UserLevelManager.is_user_type_eligible_to_delegate_to_liquidity_pool(fallback_types[0])
            ):
                return Decimal('0')

            return self.get_max_delegation(fallback_types[0])

        amount = self._calc_amount_in_token(max_delegation_in_rial)
        if amount is None:
            return self.capacity * Decimal('0.1')

        return amount

    def _calc_amount_in_token(self, amount_in_rls: Decimal) -> Union[Decimal, None]:
        if self.currency == RIAL:
            return amount_in_rls

        coin_price = PriceEstimator.get_rial_value_by_best_price(Decimal(1), self.currency, 'buy', db_fallback=True)
        if coin_price == 0:
            return

        return quantize_number(amount_in_rls / coin_price, AMOUNT_PRECISIONS_V2[self.currency])

    def get_market(self, dst_currency) -> 'Market':
        return Market.get_for(self.currency, dst_currency)

    @classmethod
    @cached_method
    def get_for(cls, src: int) -> Optional['LiquidityPool']:
        """Return pool object for the given currency"""
        return cls.objects.filter(currency=src).defer('filled_capacity').select_related('manager').first()

    def update_filled_capacity(self, amount: Decimal):
        try:
            self.filled_capacity = F('filled_capacity') + amount
            self.save(update_fields=('filled_capacity',))
        finally:
            # Remove filled_capacity F value to be queried again on further access
            del self.filled_capacity

    def get_user_delegation_limit(self, user: User) -> Decimal:
        return self.filled_capacity * self.get_user_type_delegation_limit_rate(user.user_type)

    def create_delegation(self, user, amount: Decimal) -> 'UserDelegation':
        """Delegate to pool

        Args:
            user (User): User object
            amount (Decimal): Amount to delegate

        Raises:
            PermissionDeniedException: User type is not allowed
            NoAccessException: Pool is private and user doesn't have the access
            ExceedCapacityException: Amount is larger than the unfilled capacity of pool
            LowDelegationAmountException: Amount is lower than the limit
            HighDelegationAmountException: Amount is higher than the limit
            InvalidDelegationAmount: Amount is zero or null
            InsufficientBalanceException: Amount is higher than the user's available wallet balance

        Returns:
            UserDelegation: Transaction object
        """

        from exchange.pool.models import DelegationRevokeRequest

        amount = quantize_number(amount, AMOUNT_PRECISIONS_V2[self.currency], ROUND_DOWN)
        if money_is_zero(amount):
            raise ParseError('Only positive values are allowed for monetary values.')

        result = UserLevelManager.is_eligible_to_delegate_to_liquidity_pool(user)
        if not result:
            raise PermissionDeniedException()

        if not self.has_provider_access(user):
            raise NoAccessException()

        if amount > self.unfilled_capacity:
            raise ExceedCapacityException()

        if amount < min(self.min_delegation, self.unfilled_capacity):
            raise LowDelegationAmountException()

        user_delegation, _ = UserDelegation.objects.get_or_create(pool_id=self.pk, user_id=user.id, closed_at=None)

        if amount + user_delegation.balance > self.get_max_delegation(user.user_type):
            raise HighDelegationAmountException()

        has_unpaid_revoke = DelegationRevokeRequest.objects.filter(
            status=DelegationRevokeRequest.STATUS.new,
            user_delegation__user_id=user.id,
            user_delegation__pool_id=self.pk,
        ).exists()

        if has_unpaid_revoke:
            raise DelegateWhenRevokeInProgressException()

        # May raise InvalidDelegationAmount, InsufficientBalanceException or ExceedCapacityException
        DelegationTransaction.objects.create(user_delegation=user_delegation, amount=amount)
        return user_delegation

    @staticmethod
    @cached_method  # TODO: replace with Settings caching method
    def get_user_type_delegation_limit_rate(user_type: int) -> Decimal:
        default_rate = ZERO
        for step_user_type, limit_rate in sorted(settings.NOBITEX_OPTIONS['positionLimits'].items()):
            if step_user_type <= user_type:
                default_rate = limit_rate
            else:
                break
        try:
            return Settings.get_decimal(f'pool_sell_delegation_limit_rate_{user_type}', default_rate)
        except DecimalException:
            report_exception()
        return default_rate

    def _has_user_access(self, user: User, access_type: int) -> bool:
        if not self.is_private:
            return True
        return self.pool_accesses.filter(access_type=access_type, is_active=True).filter(
            Q(user=user) | Q(user_type=user.user_type)
        ).exists()

    def has_provider_access(self, user: User) -> bool:
        return self._has_user_access(user, PoolAccess.ACCESS_TYPES.liquidity_provider)

    def has_trader_access(self, user: User) -> bool:
        return self._has_user_access(user, PoolAccess.ACCESS_TYPES.trader)

    @classmethod
    def get_pools(
        cls,
        user: User = None,
        access_type: int = None,
        check_user_has_active_alert: bool = False,
        is_active: Optional[bool] = None,
    ) -> QuerySet:

        pools = cls.objects

        is_active_q = Q(is_active=True)
        is_inactive_q = Q(is_active=False, activated_at__isnull=False)

        if is_active is True:
            pools = pools.filter(is_active_q)
        elif is_active is False:
            pools = pools.filter(is_inactive_q)
        else:
            pools = pools.filter(is_active_q | is_inactive_q)

        if user is None:
            return pools.filter(is_private=False)

        pools = pools.filter(
            Q(is_private=False)
            | (
                Q(pool_access__access_type=access_type, pool_access__is_active=True)
                & (
                    Q(pool_access__user_type=user.user_type, pool_access__user_id=None)
                    | Q(pool_access__user_type=None, pool_access__user_id=user.id)
                )
            )
        ).annotate(
            has_delegate=Exists(UserDelegation.objects.filter(user=user, pool_id=OuterRef("pk"), closed_at=None))
        )

        if check_user_has_active_alert:
            subquery = PoolUnfilledCapacityAlert.objects.filter(user=user, pool_id=OuterRef("pk"), sent_at=None)
            pools = pools.annotate(has_active_alert=Exists(subquery))

        return pools.distinct()

    def update_revoke_capacity(self, amount: Decimal):
        try:
            self.revoked_capacity = F('revoked_capacity') + amount
            self.save(update_fields=('revoked_capacity',))
        finally:
            # Remove revoked_capacity F value to be queried again on further access
            del self.revoked_capacity

    @property
    def start_date_jalali(self):
        return get_jalali_first_and_last_of_jalali_month(ir_today())[0]

    @property
    def start_date(self):
        return self.start_date_jalali.togregorian()

    @property
    def end_date_jalali(self):
        return get_jalali_first_and_last_of_jalali_month(ir_today())[1]

    @property
    def end_date(self):
        return self.end_date_jalali.togregorian()

    @property
    def profit_date(self):
        return self.end_date + timedelta(days=1)

    @property
    def profit_period(self):
        return (self.end_date - self.start_date).days + 1

    @staticmethod
    @functools.lru_cache(maxsize=1)
    def get_profit_collector():
        return User.objects.get(pk=SYSTEM_USER_IDS.system_pool_profit, username='system-pool-profit')


class PoolAccess(models.Model):
    ACCESS_TYPES = Choices(
        (1, 'liquidity_provider', 'Liquidity Provider'),
        (2, 'trader', 'Trader'),
    )
    access_type = models.SmallIntegerField(choices=ACCESS_TYPES, verbose_name='نوع دسترسی')
    user_type = models.SmallIntegerField(choices=User.USER_TYPES, null=True, blank=True, verbose_name='سطح کاربری')
    user = models.ForeignKey(
        User, related_name='+', on_delete=models.CASCADE, null=True, blank=True, verbose_name='کاربر'
    )
    liquidity_pool = models.ForeignKey(
        LiquidityPool,
        on_delete=models.CASCADE,
        related_name='pool_accesses',
        verbose_name=' استخر مشارکت',
        limit_choices_to={'is_private': True},
        related_query_name='pool_access',
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='تاریخ ایجاد')
    is_active = models.BooleanField(default=True, verbose_name='فعال؟')

    class Meta:
        verbose_name = 'سطح دسترسی به استخر مشارکت'
        verbose_name_plural = 'سطوح دسترسی به استخر مشارکت'


class UserDelegation(models.Model):
    pool = models.ForeignKey(
        LiquidityPool, on_delete=models.PROTECT, related_name='user_delegations', verbose_name='استخر'
    )
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='user_delegations', verbose_name='کاربر')
    balance = models.DecimalField(
        max_digits=BALANCE_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO, verbose_name='موجودی'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    closed_at = models.DateTimeField(verbose_name='تاریخ بسته شدن', null=True, blank=True)
    total_profit = models.DecimalField(
        max_digits=BALANCE_MAX_DIGITS, decimal_places=0, default=ZERO, verbose_name='سود کلی'
    )

    class Meta:
        verbose_name = 'کیف‌پول مشارکت'
        verbose_name_plural = 'کیف‌پول‌های مشارکت'
        constraints = (
            models.CheckConstraint(check=Q(balance__gte=0), name='delegation_non_negative_balance'),
            models.UniqueConstraint(
                fields=['pool', 'user'],
                condition=Q(closed_at=None),
                name='unique_active_user_delegation'
            ),
        )

    def __str__(self):
        return f'{self.pool.get_currency_display()}: {self.user}'

    @property
    def src_wallet(self) -> Wallet:
        return Wallet.get_user_wallet(self.user, currency=self.pool.currency)

    def update_balance(self, amount: Decimal):
        UserDelegation.objects.filter(pk=self.pk).update(
            balance=F("balance") + amount,
            closed_at=Case(When(balance__lte=-amount, then=timezone.now()), default=None),
        )

        self.refresh_from_db()
        # update liquidity-pool
        self.pool.update_filled_capacity(amount)
        if amount < 0:
            self.pool.update_revoke_capacity(amount)


class DelegationTransaction(models.Model):
    user_delegation = models.ForeignKey(
        UserDelegation, on_delete=models.PROTECT, related_name='delegations', verbose_name='کیف‌پول مشارکت'
    )
    amount = models.DecimalField(
        max_digits=TRANSACTION_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, verbose_name='مقدار'
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='تاریخ ایجاد')
    transaction = models.ForeignKey(
        Transaction, on_delete=models.SET_NULL, related_name='+', null=True, blank=True, verbose_name='تراکنش'
    )

    class Meta:
        verbose_name = 'مشارکت در استخر'
        verbose_name_plural = 'مشارکت‌های استخر'

    def clean(self):
        if not self.amount:
            raise InvalidDelegationAmount()
        if money_is_zero(abs(self.amount)):
            raise InvalidDelegationAmount()
        if self.amount < 0:
            return self.clean_negative_amount()
        return self.clean_positive_amount()

    def clean_positive_amount(self):
        if self.user_delegation.pool.unfilled_capacity < self.amount:
            raise ExceedCapacityException()
        if self.user_delegation.src_wallet.active_balance < self.amount:
            raise InsufficientBalanceException()

    def clean_negative_amount(self):
        if self.user_delegation.pool.src_wallet.active_balance + self.amount < 0:
            raise InsufficientBalanceException()

    def create_delegation_transaction(
        self,
        src_description: str,
        dst_description: str,
        src_ref: str,
        dst_ref: str,
    ) -> Transaction:
        """Transfer subscribed amount to pool wallet

        Raises:
            ValueError: If concurrency leads to wallet negative balance.
        """
        if self.transaction:
            return self.transaction

        src_transaction = self.user_delegation.src_wallet.create_transaction(
            tp="delegate", amount=-self.amount, description=src_description
        )
        dst_transaction = self.user_delegation.pool.src_wallet.create_transaction(
            tp="delegate", amount=self.amount, description=dst_description
        )
        src_transaction.commit(ref=Transaction.Ref(src_ref, self.id))
        dst_transaction.commit(ref=Transaction.Ref(dst_ref, self.id))
        return src_transaction

    def create_transaction(self):
        """Transfer subscribed amount to pool wallet"""
        if self.amount < 0:
            return self.create_delegation_transaction(
                src_description=f"لغو مشارکت در استخر {_t(get_currency_codename(self.user_delegation.pool.currency))}",
                dst_description=f"لغو مشارکت از کاربر {self.user_delegation.user}",
                src_ref="DelegationRevokeDst",
                dst_ref="DelegationRevokeSrc"
            )
        return self.create_delegation_transaction(
            src_description=f"مشارکت در استخر {_t(get_currency_codename(self.user_delegation.pool.currency))}",
            dst_description=f"مشارکت از کاربر {self.user_delegation.user}",
            src_ref="DelegationSrc",
            dst_ref="DelegationDst",
        )

    def save(self, **kwargs):
        """Save delegation

        Raises:
            AssertionError: If save is not wrapped in atomic transaction block
            PermissionError: If an attempt to change happens
        """
        assert connection.in_atomic_block
        if self.pk:
            raise PermissionError('Delegation change is forbidden')
        self.clean()
        super(DelegationTransaction, self).save(**kwargs)
        self.transaction = self.create_transaction()
        super(DelegationTransaction, self).save(update_fields=('transaction_id',))

    def _notify(self, message: str, template: str):
        Notification.objects.create(user=self.user_delegation.user, message=message)
        EmailManager.send_email(
            email=self.user_delegation.user.email,
            template=template,
            data={
                'created_at': self.transaction.created_at,
                'currency': self.user_delegation.pool.currency,
                'amount': self.amount.normalize(),
            },
            priority='medium',
        )

    def notify_on_delegation(self):
        if self.amount <= ZERO or self.transaction is None:
            return

        message = (
            f'درخواست مشارکت شما در استخر {_t(get_currency_codename(self.user_delegation.pool.currency))}'
            f' به میزان {self.amount.normalize():f} ثبت شد.'
        )
        template = 'pool/new_delegation'
        self._notify(message, template)


class DelegationRevokeRequest(models.Model):
    STATUS = Choices(
        (1, "new", "New"),
        (2, "paid", "Paid"),
    )
    amount = models.DecimalField(
        max_digits=TRANSACTION_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, verbose_name="مقدار"
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name="تاریخ ایجاد")
    status = models.SmallIntegerField(choices=STATUS, verbose_name="وضعیت", default=STATUS.new)
    delegation_transaction = models.OneToOneField(
        DelegationTransaction,
        on_delete=models.PROTECT,
        related_name="delegation_revoke_request",
        verbose_name="تراکنش لغو مشارکت",
        null=True,
        blank=True
    )
    user_delegation = models.ForeignKey(
        UserDelegation,
        on_delete=models.CASCADE,
        related_name="delegation_revoke_requests",
        verbose_name="کیف‌پول مشارکت",
        related_query_name="delegation_revoke_request",
    )

    class Meta:
        verbose_name = "درخواست لغو مشارکت"
        verbose_name_plural = "درخواست‌های لغو مشارکت"
        indexes = [
            models.Index(
                fields=("user_delegation",),
                condition=Q(status=1),
                name='delegation_revoke_request_id',
            ),
        ]

    def _notify(self, message: str, template: str):
        Notification.objects.create(user=self.user_delegation.user, message=message)
        settled_at = self.settled_at
        EmailManager.send_email(
            email=self.user_delegation.user.email,
            template=template,
            data={
                "currency": self.user_delegation.pool.currency,
                "amount": self.amount.normalize(),
                "created_at": self.created_at.date(),
                "settled_at": settled_at.date() if settled_at else None,
            },
            priority='medium',
        )

    def notify_on_paid(self):
        if self.status == self.STATUS.paid:
            message = (
                f"لغو مشارکت شما در استخر {_t(get_currency_codename(self.user_delegation.pool.currency))} "
                f"به میزان {self.amount.normalize():f} با موفقیت انجام و به کیف پول شما در نوبیتکس واریز شد."
            )
            template = "pool/delegation_revoke_on_paid"
            self._notify(message, template)

    def notify_on_new(self):
        message = (
            f"درخواست لغو مشارکت در استخر {_t(get_currency_codename(self.user_delegation.pool.currency))} "
            f"به میزان {self.amount.normalize():f} با موفقیت ثبت شد."
        )
        template = "pool/delegation_revoke_on_new"
        self._notify(message, template)

    @property
    def settled_at(self) -> Optional[datetime]:
        if self.delegation_transaction:
            return self.delegation_transaction.created_at
        return None


class PoolProfit(models.Model):
    pool = models.ForeignKey(
        LiquidityPool, verbose_name='استخر', on_delete=models.PROTECT, related_name='profits',
    )
    orders = models.ManyToManyField(
        Order, verbose_name='سفارشات تبدیل به ریال', related_name='+', blank=True,
    )
    transaction = models.ForeignKey(
        Transaction, on_delete=models.SET_NULL, related_name='+', null=True, blank=True, verbose_name='تراکنش',
    )
    from_date = models.DateField(verbose_name='تاریخ شروع')
    to_date = models.DateField(verbose_name='تاریخ پایان')
    currency = models.SmallIntegerField(choices=Currencies.subset('usdt', 'rls'), verbose_name='ارز')
    position_profit = models.DecimalField(
        verbose_name='سود حاصل از موقعیت‌ها', max_digits=TRANSACTION_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES
    )
    rial_value = models.DecimalField(
        verbose_name='سود به ریال', max_digits=TRANSACTION_MAX_DIGITS, decimal_places=0, null=True
    )

    class Meta:
        verbose_name = 'سود استخر'
        verbose_name_plural = 'سودهای استخر'
        unique_together = (('from_date', 'pool', 'currency'),)

    def __str__(self):
        return f'Pool Profit {self.id}: pool: {self.pool_id} currency: {self.currency}'

    @property
    def matched_amount(self):
        return sum(
            order.matched_amount for order in self.orders.all()
        )

    @property
    def unmatched_amount(self):
        return self.position_profit - self.matched_amount

    @classmethod
    def calc_pools_profit(
        cls, pools: 'list[LiquidityPool]', from_date: date, to_date: date
    ) -> 'dict[int, dict[int, PoolProfit]]':
        """Generate profit of pools.

        Args:
            pools (list[LiquidityPool]): Pools to generate profit for.

        Returns:
            dict[int, dict[int, PoolProfit]]: the pools with the profits

        Examples:
            {
                1: {
                    1: pool_profit1,
                    2: pool_profit2,
                },
                2: {
                    1: pool_profit1,
                    2: pool_profit2,
                },
            }
        """
        from exchange.margin.models import Position

        validate_transaction_is_atomic()
        pools_dict = {pool.currency: pool for pool in pools}
        position_profits = (
            Position.objects.annotate(
                currency=Case(When(side=Position.SIDES.sell, then=F('src_currency')), default=F('dst_currency'))
            )
            .filter(
                currency__in=pools_dict.keys(),
                closed_at__date__lte=to_date,
                closed_at__date__gte=from_date,
                pnl__isnull=False,
            )
            .values(
                'currency',
                'dst_currency',
            )
            .alias(
                profit_expr=Sum(F('earned_amount') - F('pnl'), filter=Q(earned_amount__gt=F('pnl'))),
                loss_expr=Sum(F('earned_amount') - F('pnl'), filter=Q(earned_amount__lt=F('pnl'))),
            )
            .annotate(
                profit=Coalesce(F('profit_expr'), ZERO, output_field=RoundedDecimalField()),
                loss=Coalesce(F('loss_expr'), ZERO, output_field=RoundedDecimalField()),
            )
        )

        profits = defaultdict(dict)
        for profit in position_profits:
            pool = pools_dict[profit['currency']]
            position_profit = max(
                profit['profit'] + profit['loss'],
                profit['profit'] * (1 - settings.POOL_MAX_PROFIT_REPARATION_RATE),
            )
            profits[pool.id][profit['dst_currency']] = cls.objects.update_or_create(
                pool=pool,
                currency=profit['dst_currency'],
                from_date=from_date,
                defaults=dict(to_date=to_date, position_profit=position_profit),
            )[0]

        # create PoolProfit instance with currency=RIAL for pools without RIAL profit, but non RIAL profit
        # to create its transaction properly.
        for pool_id, profit_dict in profits.items():
            if RIAL not in profit_dict:
                profits[pool_id][RIAL] = cls.objects.update_or_create(
                    pool_id=pool_id,
                    currency=RIAL,
                    from_date=from_date,
                    defaults=dict(to_date=to_date, position_profit=ZERO),
                )[0]
        return profits

    def create_convert_to_rial_order(self):
        new_order_amount = self.unmatched_amount

        if money_is_zero(new_order_amount):
            return

        open_orders = self.orders.filter(status__in=[Order.STATUS.new, Order.STATUS.active])
        if open_orders.exists():
            sleep(1)
            return

        order, error = MarketManager.create_order(
            user=self.pool.get_profit_collector(),
            src_currency=self.currency,
            dst_currency=RIAL,
            amount=new_order_amount,
            order_type=Order.ORDER_TYPES.sell,
            execution_type=Order.EXECUTION_TYPES.market,
            allow_small=True,
        )
        if error:
            report_event(f'Cannot create conversion order for pool profit {self.pk} with reason {error}')
            raise ConversionOrderException()

        self.orders.add(order)

    def create_transaction(self, amount: Decimal) -> None:
        """Transfer profit to the user wallet from pool wallet

        Raises:
            ValueError: If amount is not positive or None
            ValueError: Pool wallet balance is not enough
            ValueError: Pool wallet not exists
        """

        if self.transaction:
            return self.transaction

        if amount is None:
            raise ValueError('Invalid Amount')

        if amount <= 0:
            return None

        pool_profit_wallet = Wallet.get_user_wallet(SYSTEM_USER_IDS.system_pool_profit, currency=RIAL)
        if pool_profit_wallet is None:
            raise ValueError('Cannot reach pool profit rial wallet.')

        while amount:
            tx_amount = min(amount, TRANSACTION_MAX)
            transaction = pool_profit_wallet.create_transaction(
                tp='delegate',
                amount=-tx_amount,
                description=f'برداشت سود استخر {_t(get_currency_codename(self.pool.currency))}',
            )

            if transaction is None:
                msg = f'Pool profit has low balance on rial wallet to pay {self.pool} users profits, amount: {amount}.'
                report_event(msg)
                raise ValueError(msg)

            if not self.transaction:
                transaction.commit(ref=Transaction.Ref('DelegationProfitSrc', self.pk))
            else:
                transaction.commit(ref=Transaction.Ref('DelegationProfitSrc+', self.transaction.pk))
            amount -= tx_amount
            self.transaction = transaction


class UserDelegationProfit(models.Model):
    user_delegation = models.ForeignKey(
        UserDelegation, verbose_name='مشارکت', on_delete=models.PROTECT, related_name='profits',
    )
    transaction = models.ForeignKey(
        Transaction, on_delete=models.SET_NULL, related_name='+', null=True, blank=True, verbose_name='تراکنش',
    )
    from_date = models.DateField(verbose_name='تاریخ شروع')
    to_date = models.DateField(verbose_name='تاریخ پایان')
    delegation_score = models.DecimalField(verbose_name='امتیاز مشارکت', max_digits=25, decimal_places=10)
    amount = models.DecimalField(
        verbose_name='مقدار سود',
        max_digits=TRANSACTION_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'سود مشارکت کاربر'
        verbose_name_plural = 'سودهای مشارکت کاربر'
        unique_together = (('from_date', 'user_delegation'),)

    @property
    def settled_at(self) -> Optional[datetime]:
        if self.transaction:
            return self.transaction.created_at
        return None

    def create_transaction(self) -> None:
        """Transfer profit to the user wallet

        Raises:
            ValueError: If amount is not positive or None
        """

        if self.transaction:
            return self.transaction

        if self.amount is None:
            raise ValueError('Invalid Amount')

        if self.amount <= 0:
            return

        amount = self.amount
        while amount:
            is_positive_amount = amount > 0

            tx_amount = min(amount, TRANSACTION_MAX)
            transaction = Wallet.get_user_wallet(self.user_delegation.user, RIAL).create_transaction(
                tp='delegate',
                amount=tx_amount,
                description=f'واریز سود استخر {_t(get_currency_codename(self.user_delegation.pool.currency))}',
                allow_negative_balance=is_positive_amount,
            )
            if not self.transaction:
                transaction.commit(
                    ref=Transaction.Ref('DelegationProfitDst', self.pk),
                    allow_negative_balance=is_positive_amount,
                )
            else:
                transaction.commit(
                    ref=Transaction.Ref('DelegationProfitDst+', self.transaction.pk),
                    allow_negative_balance=is_positive_amount,
                )
            amount -= tx_amount
            self.transaction = transaction

        UserDelegation.objects.filter(pk=self.user_delegation_id).update(
            total_profit=self.user_delegation.total_profit + self.amount
        )

        db_transaction.on_commit(lambda: self.notify())

    def _notify(self, message: str, template: str):
        Notification.objects.create(user=self.user_delegation.user, message=message)
        EmailManager.send_email(
            email=self.user_delegation.user.email,
            template=template,
            data={
                'amount': format_money(self.amount, Currencies.rls, show_currency=True),
                'currency': self.user_delegation.pool.currency,
                'date': self.transaction.created_at,
            },
            priority='medium',
        )

    def notify(self):
        if not self.amount or self.amount <= ZERO or self.transaction is None:
            return

        message = (
            f'سود مشارکت در استخر {_t(get_currency_codename(self.user_delegation.pool.currency))} '
            f'به میزان {format_money(self.amount, Currencies.rls, show_currency=True)} به کیف پول شما در نوبیتکس واریز شد.'
        )
        template = 'pool/profit'
        self._notify(message, template)


class PoolUnfilledCapacityAlert(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+", verbose_name="کاربر")
    pool = models.ForeignKey(
        LiquidityPool,
        on_delete=models.CASCADE,
        verbose_name="استخر مشارکت",
        related_name="unfilled_capacity_alerts",
        related_query_name="unfilled_capacity_alert",
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name="تاریخ درخواست ارسال نوتیف")
    sent_at = models.DateTimeField(verbose_name="تاریخ ارسال نوتیف", null=True, blank=True)

    NOTIFICATION_THRESHOLD = Decimal(300_000_0)

    class Meta:
        verbose_name = "نوتیف ظرفیت خالی استخر"
        verbose_name_plural = "نوتیف‌های ظرفیت خالی استخر"
        constraints = (
            models.UniqueConstraint(
                fields=['pool', 'user'],
                condition=Q(sent_at=None),
                name='unique_active_notification'
            ),
        )

    @classmethod
    def send_alerts(cls):
        notifications = cls.objects.filter(sent_at=None, pool__is_active=True).select_related('pool', 'user')
        email_per_pool = defaultdict(list)
        user_notifications = []

        for notification in notifications:
            if PriceEstimator.get_rial_value_by_best_price(
                notification.pool.unfilled_capacity, notification.pool.currency, 'buy'
            ) > cls.NOTIFICATION_THRESHOLD and notification.pool.has_provider_access(notification.user):
                message = (
                    f'ظرفیت استخر {_t(get_currency_codename(notification.pool.currency))} افزایش پیدا کرده است.'
                    f'جهت مشارکت، لطفا به پنل کاربری خود در نوبیتکس و بخش استخر مشارکت مراجعه فرمایید.'
                )

                user_notifications.append(Notification(user=notification.user, message=message))
                email_per_pool[notification.pool.currency].append(notification.user.email)
                notification.sent_at = timezone.now()

        template = 'pool/unfilled_capacity_alert'
        for currency, emails in email_per_pool.items():
            EmailManager.send_email(
                email=emails,
                template=template,
                data={'currency': currency},
                priority='medium',
            )

        Notification.objects.bulk_create(user_notifications, batch_size=500)
        cls.objects.bulk_update(notifications, fields=['sent_at'], batch_size=500)


class PoolMinimumAvailableRatioAlert(models.Model):
    pool = models.OneToOneField(LiquidityPool, on_delete=models.CASCADE, verbose_name="استخر مشارکت")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="تاریخ ارسال نوتیف")
    is_active = models.BooleanField(default=True, verbose_name='فعال؟')

    class Meta:
        verbose_name = 'نوتیف کمینه نسبت ظرفیت دردسترس'
        verbose_name_plural = 'نوتیف‌های کمینه نسبت ظرفیت دردسترس'


class PoolStat(models.Model):
    pool = models.ForeignKey(LiquidityPool, on_delete=models.CASCADE, verbose_name='استخر مشارکت')
    from_date = models.DateField(verbose_name='تاریخ شروع')
    to_date = models.DateField(verbose_name='تاریخ پایان')
    apr = models.DecimalField(max_digits=10, decimal_places=2, null=True, verbose_name='سود تقریبی سالیانه')
    balance = models.DecimalField(
        max_digits=BALANCE_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, verbose_name='موجودی پایان دوره'
    )
    total_delegators = models.PositiveIntegerField(verbose_name='تعداد مشارکت کننده')
    avg_balance = models.DecimalField(
        max_digits=BALANCE_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
        verbose_name='نسبت کل امتیازات به تعداد روز',
    )
    capacity = models.DecimalField(
        max_digits=BALANCE_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, verbose_name='ظرفیت پایان دوره'
    )
    total_profit_in_rial = models.DecimalField(
        max_digits=BALANCE_MAX_DIGITS, decimal_places=0, verbose_name='سود کل دوره به ریال'
    )
    token_price = models.DecimalField(
        max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, verbose_name='فیمت توکن استخر'
    )

    class Meta:
        verbose_name = 'آمار استخر'
        verbose_name_plural = verbose_name


class PoolItemChange(models.Model):
    pool = models.ForeignKey(
        LiquidityPool, on_delete=models.CASCADE, verbose_name='استخر مشارکت'
    )
    name = models.TextField(verbose_name='نام فیلد')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='تاریخ تغییر')
    old_value = models.TextField(verbose_name='مقدار قبلی')
    new_value = models.TextField(verbose_name='مقدار جدید')

    class Meta:
        verbose_name = 'تغییر ایتم های استخر مشارکت'


class DelegationLimit(models.Model):
    """maximum amount that a user can be delegated in margin per (market,order_type) pair"""

    vip_level = models.PositiveSmallIntegerField()

    leverage = models.DecimalField(max_digits=2, decimal_places=1, default=Decimal(1), verbose_name='اهرم')
    market = models.ForeignKey(Market, on_delete=models.CASCADE)
    order_type = models.IntegerField(choices=Order.ORDER_TYPES, verbose_name='نوع')
    limitation = models.DecimalField(max_digits=TRANSACTION_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=(
                    'vip_level',
                    'market',
                    'order_type',
                    'leverage',
                ),
                name='unique_vip_level_and_market_per_leverage_and_order_type',
            ),
        )


class UserDelegationLimit(models.Model):
    """this will override `DelegationLimit` values per (market,order_type) pair"""

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    leverage = models.DecimalField(max_digits=2, decimal_places=1, default=Decimal(1), verbose_name='اهرم')
    market = models.ForeignKey(Market, on_delete=models.CASCADE)
    order_type = models.IntegerField(choices=Order.ORDER_TYPES, verbose_name='نوع')
    limitation = models.DecimalField(max_digits=TRANSACTION_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=('user', 'market', 'order_type', 'leverage'),
                name='unique_user_and_market_per_leverage_and_order_type',
            ),
        )
