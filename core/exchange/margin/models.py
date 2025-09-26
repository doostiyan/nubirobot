import datetime
from decimal import ROUND_DOWN, ROUND_UP, Decimal, DecimalException
from typing import Dict, Iterable, Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.db.models import Max, Min, Q
from django.utils import timezone
from django.utils.functional import cached_property
from model_utils import Choices

from exchange.accounts.constants import SYSTEM_USER_IDS
from exchange.accounts.models import Notification, User
from exchange.base.calendar import ir_today
from exchange.base.constants import MAX_PRECISION, MONETARY_DECIMAL_PLACES, ZERO
from exchange.base.emailmanager import EmailManager
from exchange.base.fields import RoundedDecimalField
from exchange.base.helpers import atomic_if_is_not_already
from exchange.base.logging import log_time, report_exception
from exchange.base.models import PRICE_PRECISIONS, Currencies, Settings, get_currency_codename
from exchange.base.money import money_is_zero
from exchange.base.strings import _t
from exchange.liquidator.models import LiquidationRequest
from exchange.market.constants import FEE_MAX_DIGITS, ORDER_MAX_DIGITS
from exchange.market.marketmanager import MarketManager
from exchange.market.models import Market, Order, OrderMatching
from exchange.pool.models import LiquidityPool
from exchange.wallet.constants import TRANSACTION_MAX_DIGITS
from exchange.wallet.models import Transaction, Wallet


class Position(models.Model):
    SIDES = Order.ORDER_TYPES
    STATUS = Choices(
        (0, 'new', 'New'),
        (1, 'open', 'Open'),
        (2, 'closed', 'Closed'),
        (3, 'liquidated', 'Liquidated'),
        (4, 'canceled', 'Canceled'),
        (5, 'expired', 'Expired'),
    )
    MARGIN_TYPE = Choices(
        (1, 'isolated', 'Isolated Margin'),
        (2, 'cross', 'Cross Margin'),
    )
    BASE_LEVERAGE = Decimal(1)
    MAX_MARGIN_RATIO = Decimal(999)

    STATUS_ONGOING = (STATUS.new, STATUS.open)

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='positions', verbose_name='کاربر')
    src_currency = models.SmallIntegerField(choices=Currencies, verbose_name='ارز مبدا')
    dst_currency = models.SmallIntegerField(choices=Currencies.subset('usdt', 'rls'), verbose_name='ارز مقصد')
    side = models.SmallIntegerField(choices=SIDES, verbose_name='جهت')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='تاریخ ایجاد')
    opened_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ باز شدن')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ بسته شدن')
    freezed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ متوقف (لیکویید یا منقضی) شدن')
    status = models.SmallIntegerField(choices=STATUS, default=STATUS.new, verbose_name='وضعیت')

    margin_type = models.SmallIntegerField(choices=MARGIN_TYPE, default=MARGIN_TYPE.isolated, verbose_name='نوع وثیقه')
    leverage = models.DecimalField(max_digits=2, decimal_places=1, default=BASE_LEVERAGE, verbose_name='اهرم')
    # Amount in dst_currency blocked from user margin wallet
    collateral = RoundedDecimalField(
        max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, verbose_name='وثیقه'
    )
    # Amount in src_currency borrowed for the position
    delegated_amount = models.DecimalField(
        max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=0, verbose_name='مقدار وکالت‌گرفته'
    )
    # Amount in dst_currency bought through position trades, kept in pool wallet on behalf of user
    earned_amount = models.DecimalField(
        max_digits=ORDER_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
        default=0,
        verbose_name='مقدار دریافتی از معاملات',
    )
    liquidation_price = RoundedDecimalField(
        max_digits=ORDER_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
        null=True,
        blank=True,
        verbose_name='قیمت انحلال',
    )
    entry_price = RoundedDecimalField(
        max_digits=ORDER_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
        null=True,
        blank=True,
        verbose_name='میانگین قیمت باز شدن',
    )
    exit_price = RoundedDecimalField(
        max_digits=ORDER_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
        null=True,
        blank=True,
        verbose_name='میانگین قیمت بسته شدن',
    )

    orders = models.ManyToManyField(
        Order,
        through='PositionOrder',
        related_query_name='position',
        verbose_name='سفارش‌ها',
    )
    liquidation_requests = models.ManyToManyField(
        LiquidationRequest,
        through='PositionLiquidationRequest',
        related_name='+',
        verbose_name='درخواست‌های لیکویید کردن',
    )

    pnl = RoundedDecimalField(
        max_digits=TRANSACTION_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
        null=True,
        blank=True,
        verbose_name='سود و زیان',
    )
    pnl_transaction = models.ForeignKey(
        Transaction,
        on_delete=models.SET_NULL,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='تراکنش PNL',
    )

    class Meta:
        verbose_name = 'موقعیت'
        verbose_name_plural = 'موقعیت‌ها'
        constraints = (models.CheckConstraint(check=Q(collateral__gte=0), name='position_positive_collateral'),)
        indexes = (
            # To use in user delegation limit and position list
            models.Index(
                fields=('user', 'side', 'src_currency', 'dst_currency'),
                condition=Q(pnl__isnull=True),
                name='user_active_positions',
            ),
            # To use in liquidating positions
            models.Index(
                fields=('src_currency', 'dst_currency', 'side', 'liquidation_price'),
                condition=Q(status=1),
                name='idx_liquidate_positions',
            ),
            # To use in position fee, expiry and liquidation/expiration settlement
            models.Index(
                fields=('status', 'created_at'),
                condition=Q(pnl__isnull=True),
                name='system_active_positions',
            ),
            # To use in pool profit calculations
            models.Index(
                fields=('side', 'src_currency', 'dst_currency', 'closed_at'),
                condition=Q(pnl__isnull=False),
                name='system_past_positions',
            ),
            # To use in canceled position clean up
            models.Index(
                fields=('id',),
                condition=Q(status=4),
                name='system_canceled_positions',
            ),
            # To use in `LiquidityPool.unblocked_balance`
            models.Index(
                fields=('side', 'earned_amount', 'pnl', 'pnl_transaction'),
                condition=(
                    # use `Order.ORDER_TYPES.buy` instead of `Position.SIDES.buy` since they are equal
                    Q(side=Order.ORDER_TYPES.buy)
                    & (Q(pnl__isnull=True) | (Q(pnl__isnull=False) & Q(pnl__gt=0) & Q(pnl_transaction__isnull=True)))
                    & Q(earned_amount__gt=0)
                ),
                name='idx_pool_unsettled_positions',
            ),
            # To use in `create_pool_pnl_transactions` command
            models.Index(
                fields=('id',),
                name='idx_margin_position_unsettled1',
                condition=(Q(pnl_transaction__isnull=True, pnl__isnull=False) & ~Q(pnl=0)),
            ),
        )

    @cached_property
    def _calculator(self):
        from exchange.margin.services import LongCalculator, ShortCalculator

        return ShortCalculator(self) if self.is_short else LongCalculator(self)

    @property
    def total_asset(self):
        return self._calculator.get_total_asset()

    @cached_property
    def market(self) -> Market:
        return Market.get_for(self.src_currency, self.dst_currency)

    @cached_property
    def is_short(self) -> Market:
        return self.side == Position.SIDES.sell

    @cached_property
    def trade_fee_rate(self) -> Decimal:
        return MarketManager.get_trade_fee(self.market, self.user, amount=1, is_maker=False)

    @cached_property
    def cached_orders(self) -> Iterable[Order]:
        return self.orders.all()

    @cached_property
    def cached_liquidation_requests(self) -> Iterable[LiquidationRequest]:
        if self.freezed_at:
            return self.liquidation_requests.all()
        return self.liquidation_requests.none()

    @property
    def open_side_orders(self) -> Iterable[Order]:
        return (order for order in self.cached_orders if order.order_type == self.side)

    @property
    def close_side_orders(self) -> Iterable[Order]:
        return (order for order in self.cached_orders if order.order_type != self.side)

    def set_delegated_amount(self):
        sold = sum((order.matched_amount for order in self.cached_orders if order.is_sell), ZERO)
        bought = sum((order.matched_amount - order.fee for order in self.cached_orders if order.is_buy), ZERO)
        if self.is_short:
            bought += self._calculator.get_system_settled_amount()
        else:
            sold -= self._calculator.get_system_settled_amount()
        self.delegated_amount = max(sold - bought if self.is_short else bought - sold, ZERO)
        if sold and bought and not self.delegated_amount and round(abs(sold / bought - 1), 2) != 0:
            Notification.notify_admins(
                f'Check out position #{self.id} for {self.user.email} in {self.market.symbol}\n{sold} vs {bought}',
                title='‼️‼️‼️ Certain double spend in margin',
                channel='pool',
            )

    @property
    def liability(self):
        return self._calculator.get_liability()

    @property
    def settled_amount(self) -> Decimal:
        return sum((order.matched_amount for order in self.close_side_orders), ZERO) + abs(
            self._calculator.get_system_settled_amount()
        )

    def set_earned_amount(self):
        self.earned_amount = sum((
            order.matched_total_price - order.fee if order.is_sell else -order.matched_total_price
            for order in self.cached_orders
        ), ZERO) + self._calculator.get_system_settled_total_price()

    def set_liquidation_price(self):
        if not self.liability or money_is_zero(self.liability) or self.status == self.STATUS.liquidated:
            return
        precision = PRICE_PRECISIONS.get(self.market.symbol)
        self.liquidation_price = self._calculator.get_liquidation_price(precision)

    @property
    def initial_margin_ratio(self) -> Decimal:
        value = 1 + 1 / self.leverage
        return value.quantize(Decimal('1E-2'), rounding=ROUND_DOWN)

    @property
    def margin_ratio(self) -> Optional[Decimal]:
        if not self._calculator.market_price:
            return None
        value = self._calculator.get_margin_ratio()
        if value:
            value = min(value, self.MAX_MARGIN_RATIO)
            return value.quantize(Decimal('1E-2'), rounding=ROUND_DOWN)

    @property
    def asset_in_order(self) -> Decimal:
        return sum((order.unmatched_total_price for order in self.close_side_orders if order.blocks_balance), ZERO)

    @property
    def liability_in_order(self) -> Decimal:
        return sum((order.unmatched_amount for order in self.close_side_orders if order.blocks_balance), ZERO)

    @property
    def delegation_total_price(self) -> Decimal:
        return self._calculator.get_delegation_total_price()

    @cached_property
    def expiration_date(self) -> datetime.date:
        return self.created_at.astimezone().date() + timezone.timedelta(days=settings.POSITION_EXTENSION_LIMIT + 1)

    def set_status(self):
        """Change status via state machine

        new ---> canceled
           `---> open ---> closed
           `         `---> liquidated
           `---------`===> expired
        """
        if self.status == self.STATUS.new:
            if any(order.matched_amount for order in self.cached_orders):
                self.status = self.STATUS.open
            elif all(order.status == Order.STATUS.canceled for order in self.cached_orders):
                self.status = self.STATUS.canceled
        if self.status == self.STATUS.open:
            if money_is_zero(self.liability) and all(order.is_closed for order in self.cached_orders):
                self.status = self.STATUS.closed
            elif (margin_ratio := self.margin_ratio) and margin_ratio < settings.MAINTENANCE_MARGIN_RATIO:
                self.status = self.STATUS.liquidated
        if self.status in self.STATUS_ONGOING and ir_today() >= self.expiration_date:
            self.status = self.STATUS.expired

    def set_opened_at(self):
        if self.opened_at or self.status == self.STATUS.new:
            return
        self.opened_at = OrderMatching.objects.filter(
            **{f'{"sell" if self.is_short else "buy"}_order__in': self.open_side_orders},
        ).aggregate(first_time=Min('created_at'))['first_time']

    def set_closed_at(self):
        if self.closed_at or self.status in self.STATUS_ONGOING or not money_is_zero(self.liability):
            return
        if self.cached_liquidation_requests:
            self.closed_at = max(liq_quest.updated_at for liq_quest in self.cached_liquidation_requests)
        else:
            self.closed_at = OrderMatching.objects.filter(
                **{f'{"buy" if self.is_short else "sell"}_order__in': self.close_side_orders},
            ).aggregate(last_time=Max('created_at'))['last_time']

    def set_freezed_at(self):
        if self.freezed_at:
            return
        if self.status in self.STATUS.subset('liquidated', 'expired'):
            self.freezed_at = timezone.now()

    @staticmethod
    def get_user_share(extension_days: int, *, profit: bool = False):
        """Get user share of PNL

        In case of loss, user is fully accountable, and his share is 1.
        By each day the position is extended, pool gains 1% of the final profit up to 30 days.
        Args:
            extension_days: How many days passed since position was created
                    A non-negative number at most equal to POSITION_EXTENSION_LIMIT -- currently 30
            profit: Whether ended in profit or loss

        Returns: User share of PNL as a number in range [0, 1]
        """
        if not profit:
            return 1

        return max(1 - Decimal('0.01') * (extension_days + 1), ZERO)

    def get_user_pnl(self, total_pnl: Decimal, closed_at: datetime.datetime):

        extension_days = min(
            (closed_at.astimezone().date() - self.created_at.astimezone().date()).days,
            settings.POSITION_EXTENSION_LIMIT,
        )
        return total_pnl * self.get_user_share(extension_days, profit=total_pnl > 0)

    def set_pnl(self):
        if self.pnl is not None or self.status in self.STATUS_ONGOING or not money_is_zero(self.liability):
            return
        if self.closed_at and self.freezed_at:
            log_time(
                'margin_system_settlement_interval_milliseconds',
                time=(self.closed_at - self.freezed_at).seconds * 1000,
                labels=(self.get_status_display(),),
            )

        if not self.opened_at:
            self.pnl = 0
        else:
            self.pnl = self.get_user_pnl(self.earned_amount, self.closed_at)

        if self.pnl + self.collateral < 0:
            final_margin_ratio = ZERO
            if self.collateral:
                final_margin_ratio = self.initial_margin_ratio + self.earned_amount / self.collateral / self.leverage
            Notification.notify_admins(
                f'We missed to liquidate and settle #{self.id} in time.\n'
                f'Position margin ratio on closing is {final_margin_ratio:.4f} '
                f'rather than {settings.MAINTENANCE_MARGIN_RATIO}, which led to pool loss.',
                title=f'‼️Pool Loss - {self.market.symbol}',
                channel='pool',
            )
            self.pnl = - self.collateral

        user_wallet = Wallet.get_user_wallet(self.user, self.dst_currency, tp=Wallet.WALLET_TYPE.margin)
        if self.pnl + user_wallet.balance < 0:
            Notification.notify_admins(
                f'Insufficient Margin Balance: {self.pnl + user_wallet.balance} {self.market.symbol}',
                title='‼️Position Settlement',
                channel='pool',
            )
            self.pnl = - user_wallet.balance

        self._create_pnl_transaction(user_wallet)
        user_wallet.unblock(self.collateral)

    @property
    def pnl_transaction_description(self):
        return (
            f'{"واریز سود" if self.pnl > 0 else "تسویه ضرر"} موقعیت {_t(self.get_side_display())} '
            f'{_t(get_currency_codename(self.src_currency))}'
        )

    @atomic_if_is_not_already
    def _create_pnl_transaction(self, user_wallet: Wallet) -> Optional[Transaction]:
        if not self.pnl or self.pnl_transaction:
            return self.pnl_transaction

        user_transaction = user_wallet.create_transaction(
            tp='pnl', amount=self.pnl, description=self.pnl_transaction_description
        )
        user_transaction.commit(ref=Transaction.Ref('PositionUserPNL', self.id))

        return user_transaction

    @property
    def pnl_percent(self) -> Decimal:
        if not self.pnl:
            return ZERO
        total_pnl_percent = self._calculator.get_total_pnl_percent(self.exit_price)
        return self.get_user_pnl(total_pnl_percent, self.closed_at).quantize(Decimal('0E-2'))

    @property
    def unrealized_pnl(self) -> Decimal:
        if not self._calculator.market_price:
            return ZERO
        unrealized_total_pnl = self._calculator.get_unrealized_total_pnl()
        return self.get_user_pnl(unrealized_total_pnl, timezone.now())

    @property
    def unrealized_exit_price(self) -> Decimal:
        unrealized_rate = 1 / (1 + self.settled_amount / self.liability)
        return self._calculator.market_price * unrealized_rate + (self.exit_price or 0) * (1 - unrealized_rate)

    @property
    def unrealized_pnl_percent(self) -> Decimal:
        market_price = self._calculator.market_price
        if not market_price or not self.delegated_amount:
            return ZERO
        total_pnl_percent = self._calculator.get_total_pnl_percent(self.unrealized_exit_price)
        return self.get_user_pnl(total_pnl_percent, timezone.now()).quantize(Decimal('0E-2'))

    def set_entry_price(self):
        self.entry_price = self._calculator.get_entry_price()

    def set_exit_price(self):
        self.exit_price = self._calculator.get_exit_price()

    def notify_on_complete(self) -> str:
        side = _t(self.get_side_display())
        if self.status == Position.STATUS.liquidated:
            message = f'موقعیت {side} شما بر روی {self.market.market_display} لیکوئید شد'
            template = 'liquidation_call'
        elif self.status == Position.STATUS.expired:
            message = f'موقعیت {side} شما بر روی {self.market.market_display} منقضی شد'
            template = 'position_expired'
        else:
            return
        Notification.objects.create(user=self.user, message=message)
        EmailManager.send_email(
            email=self.user.email,
            template=template,
            data={
                'is_short': self.is_short,
                'market_display': self.market.market_display,
                'closed_at_date': self.closed_at.astimezone().date() if self.closed_at else None,
                'closed_at': self.closed_at.astimezone() if self.closed_at else None,
                'exit_price': self.exit_price,
                'extension_fee_amount': self.extension_fee_amount,
                'collateral': self.collateral,
                'created_at': self.created_at.astimezone().date(),
            },
            priority='medium',
        )

    @classmethod
    def bulk_notify_on_complete(cls, positions: Iterable["Position"]):
        notifs_to_be_created = []
        emails_to_be_sent = []
        for position in positions:
            side = _t(position.get_side_display())
            if position.status == Position.STATUS.liquidated:
                message = f'موقعیت {side} شما بر روی {position.market.market_display} لیکوئید شد'
                template = 'liquidation_call'
            elif position.status == Position.STATUS.expired:
                message = f'موقعیت {side} شما بر روی {position.market.market_display} منقضی شد'
                template = 'position_expired'
            else:
                continue
            notifs_to_be_created.append(Notification(user=position.user, message=message))
            emails_to_be_sent.extend(
                EmailManager.create_email(
                    email=position.user.email,
                    template=template,
                    data={
                        'is_short': position.is_short,
                        'market_display': position.market.market_display,
                        'closed_at_date': position.closed_at.astimezone().date() if position.closed_at else None,
                        'closed_at': position.closed_at.astimezone() if position.closed_at else None,
                        'exit_price': position.exit_price,
                        'extension_fee_amount': position.extension_fee_amount,
                        'collateral': position.collateral,
                        'created_at': position.created_at.astimezone().date(),
                    },
                    priority='medium',
                )
            )
        Notification.objects.bulk_create(notifs_to_be_created)
        EmailManager.send_mail_many(emails_to_be_sent)

    @property
    def extension_fee_amount(self):
        return PositionFee.get_amount(self.src_currency, self.dst_currency, self.side, self.delegation_total_price)

    def check_daily_fee(self):
        if self.status not in self.STATUS_ONGOING:
            return
        today = ir_today()
        create_date = self.created_at.astimezone().date()
        if not create_date < today < self.expiration_date:
            return
        last_fee = self.fees.order_by('date').last()
        if not last_fee or last_fee.date != today:
            from .crons import EXTEND_CRON_LOCK
            if not EXTEND_CRON_LOCK.get_running_lock_date():
                Notification.notify_admins(
                    f'Uncollected Fee for #{self.pk} since {last_fee.date if last_fee else self.created_at}',
                    title='‼️Position',
                    channel='pool',
                )
            PositionFee.objects.get_or_create(position=self, date=today)


class PositionOrder(models.Model):
    """One-to-Many relation between Position and Order"""
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='+', verbose_name='موقعیت')
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='+', verbose_name='سفارش')
    blocked_collateral = models.DecimalField(
        max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, null=True, verbose_name='وثیقه سفارش'
    )


class PositionLiquidationRequest(models.Model):
    """One-to-Many relation between Position and LiquidationRequest"""

    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='+', verbose_name='موقعیت')
    liquidation_request = models.OneToOneField(
        LiquidationRequest, on_delete=models.CASCADE, related_name='+', verbose_name='درخواست لیکویید کردن'
    )
    is_processed = models.BooleanField(default=False, verbose_name='پردازش شده؟')

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=('position',),
                condition=Q(is_processed=False),
                name='unique_unprocessed_liquidation_request_per_position',
            ),
        )


class PositionFee(models.Model):
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name='fees', verbose_name='موقعیت')
    date = models.DateField(default=ir_today, verbose_name='تاریخ')
    amount = models.DecimalField(
        max_digits=FEE_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, verbose_name='مقدار'
    )
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name='+',
        null=True,
        blank=True,
        verbose_name='تراکنش',
    )

    class Meta:
        verbose_name = 'کارمزد موقعیت'
        verbose_name_plural = 'کارمزدهای موقعیت'
        unique_together = ('position', 'date')

    def clean(self):
        if not self.position:
            raise ValidationError('Position is required')
        if self.position.pnl is not None:
            raise ValidationError('Position is already settled')

    def save(self, *, force_insert=False, force_update=False, using=None, update_fields=None):
        if not self.pk:
            self.clean()
            self.amount = self.position.extension_fee_amount
            if update_fields:
                update_fields = (*update_fields, 'amount')

            if self.amount > self.position.collateral:
                return
        super().save(force_insert, force_update, using, update_fields)
        self.commit()

    @classmethod
    def get_amount(cls, src_currency: int, dst_currency: int, side: int, delegation_total_price: Decimal) -> Decimal:
        unit = settings.NOBITEX_OPTIONS['positionFeeUnits'][dst_currency]
        shares = (delegation_total_price / unit).to_integral(ROUND_UP)
        return shares * unit * cls.get_fee_rate(src_currency if side == Position.SIDES.sell else dst_currency)

    @staticmethod
    def get_fee_rate(pool_currency: int) -> Decimal:
        try:
            fee_rate = Settings.get_decimal(f'{Settings.CACHEABLE_PREFIXES.position_fee_rate.value}_{pool_currency}')
            return fee_rate.quantize(MAX_PRECISION)
        except DecimalException:
            report_exception()
        return ZERO

    @staticmethod
    def fetch_fee_rates(pool_currencies: Iterable[int]) -> Dict[int, Decimal]:
        """this function map currency ids to their fee rates"""
        pool_cache_keys = {
            pool_currency: f'{Settings.CACHEABLE_PREFIXES.position_fee_rate.value}_{pool_currency}'
            for pool_currency in pool_currencies
        }
        fee_rates = Settings.get_many(list(pool_cache_keys.values()), '0')

        pool_currency_to_fee_rates: Dict[int, Decimal] = {}
        for pool_currency, pool_cache_key in pool_cache_keys.items():
            fee_rate = fee_rates.get(pool_cache_key)
            try:
                pool_currency_to_fee_rates[pool_currency] = Decimal(fee_rate)
                pool_currency_to_fee_rates[pool_currency].quantize(MAX_PRECISION)
            except DecimalException:
                pool_currency_to_fee_rates[pool_currency] = ZERO
                report_exception()

        return pool_currency_to_fee_rates

    def commit(self):
        assert connection.in_atomic_block
        if self.transaction_id or not self.amount:
            return

        side = _t(self.position.get_side_display())
        description = f'کارمزد تمدید حق {side} تعهدی {_t(get_currency_codename(self.position.src_currency))}'

        user_wallet = Wallet.get_user_wallet(self.position.user, self.position.dst_currency, Wallet.WALLET_TYPE.margin)
        src_transaction = user_wallet.create_transaction(tp='fee', amount=-self.amount, description=description)
        src_transaction.commit(ref=Transaction.Ref('PositionFeeSrc', self.id))
        self.transaction = src_transaction
        self.save(update_fields=('transaction',))

        self.position.collateral -= self.amount
        self.position.set_liquidation_price()
        self.position.save(update_fields=('collateral', 'liquidation_price'))

        user_wallet.unblock(self.amount)


class MarginCall(models.Model):
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='margin_calls', verbose_name='موقعیت')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='تاریخ ایجاد')
    market_price = models.DecimalField(
        max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, verbose_name='قیمت بازار'
    )
    liquidation_price = models.DecimalField(
        max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, verbose_name='قیمت انحلال'
    )
    is_sent = models.BooleanField(default=False, verbose_name='ارسال شده؟')
    is_solved = models.BooleanField(default=False, verbose_name='برطرف شده؟')

    class Meta:
        verbose_name = 'اعلان موقعیت'
        verbose_name_plural = 'اعلان‌های موقعیت'

    def send(self):
        if self.is_sent:
            return
        side = _t(self.position.get_side_display())
        Notification.objects.create(
            user=self.position.user,
            message=f'موقعیت {side} شما بر روی {self.position.market.market_display} نزدیک به نقطه لیکوئید شدن است',
        )
        EmailManager.send_email(
            email=self.position.user.email,
            template='margin_call',
            data={
                'is_short': self.position.is_short,
                'market_display': self.position.market.market_display,
                'price_diff_percent': self.price_diff_percent,
                'price_diff_threshold': 0,
                'leverage': self.position.leverage.normalize(),
                'liability': self.position.liability.normalize(),
                'liquidation_price': self.liquidation_price.normalize(),
                'domain': settings.PROD_FRONT_URL,
            },
            priority='high',
        )
        self.is_sent = True
        self.save(update_fields=('is_sent',))

    @classmethod
    def bulk_send(cls, margin_call_objects):
        notifs_to_be_created = []
        emails_to_be_sent = []
        margin_call_to_be_updated = list(filter(lambda m: not m.is_sent, margin_call_objects))
        for margin_call in margin_call_to_be_updated:
            side = _t(margin_call.position.get_side_display())
            notifs_to_be_created.append(
                Notification(
                    user=margin_call.position.user,
                    message=f'موقعیت {side} شما بر روی {margin_call.position.market.market_display} نزدیک به نقطه لیکوئید شدن است',
                )
            )
            emails_to_be_sent.extend(
                EmailManager.create_email(
                    email=margin_call.position.user.email,
                    template='margin_call',
                    data={
                        'is_short': margin_call.position.is_short,
                        'market_display': margin_call.position.market.market_display,
                        'price_diff_percent': margin_call.price_diff_percent,
                        'price_diff_threshold': 0,
                        'leverage': margin_call.position.leverage.normalize(),
                        'liability': margin_call.position.liability.normalize(),
                        'liquidation_price': margin_call.liquidation_price.normalize(),
                        'domain': settings.PROD_FRONT_URL,
                    },
                    priority='high',
                )
            )
            margin_call.is_sent = True

        EmailManager.send_mail_many(emails_to_be_sent)
        Notification.objects.bulk_create(notifs_to_be_created)
        MarginCall.objects.bulk_update(margin_call_to_be_updated, fields=['is_sent'])

    @property
    def price_diff_percent(self) -> int:
        return int(abs(self.liquidation_price / self.market_price - 1) * 100)


class PositionCollateralChange(models.Model):
    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name='collateral_changes',
        verbose_name='موقعیت',
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='تاریخ ایجاد')
    old_value = RoundedDecimalField(
        max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, verbose_name='مقدار قبلی'
    )
    new_value = RoundedDecimalField(
        max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, verbose_name='مقدار جدید'
    )

    class Meta:
        verbose_name = 'تغییر وثیقه موقعیت'
        verbose_name_plural = 'تغییرات وثیقه موقعیت'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.position and not self.old_value:
            self.old_value = self.position.collateral

    def save(self, *, force_insert=False, force_update=False, using=None, update_fields=None):
        if not self.new_value:
            self.new_value = self.position.collateral
            if update_fields:
                update_fields = (*update_fields, 'new_value')

        super().save(force_insert, force_update, using, update_fields)


class MarginOrderChange(models.Model):
    """Track margin order changes"""
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='untracked_changes', verbose_name='سفارش')
