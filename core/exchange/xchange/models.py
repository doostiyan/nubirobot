""" Xchange Models """
import datetime
import decimal
from typing import Any, ClassVar, Optional

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import QuerySet
from django.db.models.aggregates import Sum
from django.db.models.functions import Coalesce
from model_utils import Choices

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.constants import MONETARY_DECIMAL_PLACES, ZERO
from exchange.base.models import Currencies
from exchange.config.config.derived_data import XCHANGE_TESTING_CURRENCIES
from exchange.wallet.constants import BALANCE_MAX_DIGITS, TRANSACTION_MAX_DIGITS
from exchange.wallet.models import Transaction
from exchange.xchange.limitation import DefaultStrategyInLimitation, USDTRLSStrategyInLimitation


class ExchangeTradeManager(models.Manager):
    def create(self, **kwargs: Any) -> Any:
        if 'amount' in kwargs:
            for key in ['amount', 'price']:
                if isinstance(kwargs.get(key), str):
                    kwargs[key] = decimal.Decimal(kwargs[key])
            kwargs['src_amount'] = kwargs.get('amount')
            kwargs['dst_amount'] = kwargs.get('price') * kwargs.get('amount')
            kwargs['quote_id'] = kwargs.get('settlement_reference')
            kwargs.pop('amount', None)
            kwargs.pop('price', None)
            kwargs.pop('settlement_reference', None)
        return super().create(**kwargs)


class ExchangeTrade(models.Model):
    """ Direct Xchange Trade
    """
    STATUS = Choices(
        (0, 'unknown', 'نامعلوم'),
        (10, 'succeeded', 'موفق'),
        (20, 'failed', 'ناموفق'),
    )
    USER_AGENT = Choices(
        (0, 'unknown', 'unknown'),
        (1, 'android', 'Android'),
        (2, 'android_lite', 'Android-lite'),
        (3, 'android_pro', 'Android-pro'),
        (4, 'ios', 'IOS'),
        (5, 'mozilla', 'Mozilla'),
        (6, 'safari', 'Safari'),
        (7, 'opera', 'Opera'),
        (8, 'edge', 'Edge'),
        (9, 'chrome', 'Chrome'),
        (10, 'firefox', 'Firefox'),
        (11, 'samsung_internet', 'Samsung Internet'),
        (12, 'api', 'API'),
        (13, 'system', 'System'),
    )

    user = models.ForeignKey(User, verbose_name='کاربر', on_delete=models.CASCADE)
    user_agent = models.IntegerField(choices=USER_AGENT, null=True, blank=True)

    created_at = models.DateTimeField(default=ir_now, db_index=True)
    status = models.SmallIntegerField(choices=STATUS, default=STATUS.unknown)

    is_sell = models.BooleanField()  # True if user is the seller
    src_currency = models.IntegerField(choices=Currencies, verbose_name='ارز مبدا')
    dst_currency = models.IntegerField(choices=Currencies, verbose_name='ارز مقصد')

    src_amount = models.DecimalField(max_digits=20, decimal_places=10)
    dst_amount = models.DecimalField(max_digits=20, decimal_places=10)

    src_transaction = models.ForeignKey(
        Transaction, null=True, blank=True, related_name='+', on_delete=models.SET_NULL,
    )
    dst_transaction = models.ForeignKey(
        Transaction, null=True, blank=True, related_name='+', on_delete=models.SET_NULL,
    )
    quote_id = models.CharField(max_length=64)
    client_order_id = models.CharField(max_length=64)
    convert_id = models.CharField(max_length=255, blank=True, null=True)
    system_src_transaction = models.ForeignKey(
        Transaction, null=True, blank=True, related_name='+', on_delete=models.SET_NULL,
    )
    system_dst_transaction = models.ForeignKey(
        Transaction, null=True, blank=True, related_name='+', on_delete=models.SET_NULL,
    )

    objects = ExchangeTradeManager()

    class Meta:
        verbose_name = 'معامله صرافی'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=('src_currency', 'dst_currency', 'created_at', 'status', 'is_sell', 'user_id')),
            models.Index(fields=('created_at',)),
        ]

    @property
    def status_code(self):
        return dict(map(lambda e: e[:2], self.STATUS._triples))[self.status]

    @property
    def price(self):
        return decimal.Decimal(self.dst_amount / self.src_amount)

    @property
    def amount(self):
        return self.src_amount


class MarketStatusManager(models.Manager):
    def get_available_markets_statuses(self) -> QuerySet:
        return self.filter(
            updated_at__gte=ir_now() - datetime.timedelta(minutes=MarketStatus.EXPIRATION_TIME_IN_MINUTES),
            status=MarketStatus.STATUS_CHOICES.available,
        )

    def get_available_market_statuses_based_on_side_filter(self, *, is_sell: bool) -> QuerySet:
        side_condition = models.Q(exchange_side=MarketStatus.EXCHANGE_SIDE_CHOICES.both_side) | (
            models.Q(exchange_side=MarketStatus.EXCHANGE_SIDE_CHOICES.sell_only)
            if is_sell
            else models.Q(exchange_side=MarketStatus.EXCHANGE_SIDE_CHOICES.buy_only)
        )
        return self.get_available_markets_statuses().filter(side_condition)

class MarketStatus(models.Model):
    objects: MarketStatusManager = MarketStatusManager()

    STATUS_CHOICES = Choices(
        (1, 'available', 'Available'),
        (2, 'unavailable', 'Unavailable'),
        (3, 'delisted', 'Delisted'),
    )

    EXCHANGE_SIDE_CHOICES = Choices(
        (1, 'both_side', 'both_side'),
        (2, 'buy_only', 'buy_only'),
        (3, 'sell_only', 'sell_only'),
        (4, 'closed', 'closed'),
    )

    EXPIRATION_TIME_IN_MINUTES = 5

    base_currency = models.IntegerField(choices=Currencies)
    quote_currency = models.IntegerField(choices=Currencies)
    base_to_quote_price_buy = models.DecimalField(max_digits=25, decimal_places=10)
    quote_to_base_price_buy = models.DecimalField(max_digits=25, decimal_places=10)
    base_to_quote_price_sell = models.DecimalField(max_digits=25, decimal_places=10)
    quote_to_base_price_sell = models.DecimalField(max_digits=25, decimal_places=10)
    min_base_amount = models.DecimalField(max_digits=20, decimal_places=10)
    max_base_amount = models.DecimalField(max_digits=20, decimal_places=10)
    min_quote_amount = models.DecimalField(max_digits=20, decimal_places=10)
    max_quote_amount = models.DecimalField(max_digits=20, decimal_places=10)
    base_precision = models.DecimalField(max_digits=20, decimal_places=10)
    quote_precision = models.DecimalField(max_digits=20, decimal_places=10)
    status = models.SmallIntegerField(choices=STATUS_CHOICES)
    exchange_side = models.SmallIntegerField(choices=EXCHANGE_SIDE_CHOICES, default=EXCHANGE_SIDE_CHOICES.both_side)
    created_at = models.DateTimeField(default=ir_now)
    updated_at = models.DateTimeField(default=ir_now, db_index=True)

    class Meta:
        verbose_name = 'وضعیت زوج ارز'
        verbose_name_plural = 'وضعیت زوج ارزها'
        constraints = [
            models.UniqueConstraint(fields=('base_currency', 'quote_currency'), name='base_quote_unique_together')
        ]
        indexes = [models.Index(fields=('base_currency', 'quote_currency'))]

    def save(self, *args, update_fields=None, **kwargs) -> None:
        self.updated_at = ir_now()
        if update_fields:
            update_fields = (*update_fields, 'updated_at')

        super().save(*args, update_fields=update_fields, **kwargs)

    @classmethod
    def get_all_markets_statuses(cls, with_beta_markets: bool = True) -> QuerySet:
        if with_beta_markets:
            return cls.objects.all()
        return cls.objects.exclude(base_currency__in=XCHANGE_TESTING_CURRENCIES)

    @classmethod
    def get_market_status(
        cls,
        base_currency: int,
        quote_currency: int,
    ) -> Optional['MarketStatus']:
        try:
            market_status = cls.objects.get(
                base_currency=base_currency,
                quote_currency=quote_currency,
            )
        except ObjectDoesNotExist:
            return None

        return market_status

    @classmethod
    def get_available_market_status_based_on_side_filter(
        cls,
        base_currency: int,
        quote_currency: int,
        *,
        is_sell: bool,
    ) -> Optional['MarketStatus']:
        try:
            available_markets = cls.objects.get_available_market_statuses_based_on_side_filter(is_sell=is_sell)

            market_status = available_markets.get(
                base_currency=base_currency,
                quote_currency=quote_currency,
            )
        except ObjectDoesNotExist:
            return None

        return market_status

    def has_user_exceeded_limit(
        self, user_id: int, amount: decimal.Decimal, is_sell: bool, reference_currency: int
    ) -> bool:
        """
        Checks if a user has exceeded this market limit.
        :param user_id: The ID of the user.
        :param amount: The amount of the transaction.
        :param is_sell: Whether the transaction is a sell.
        :param reference_currency: The currency in which the amount is referenced.
        :return: True if the user has exceeded the limit, False otherwise.
        """

        return self._has_limit_exceeded(
            amount=amount,
            is_sell=is_sell,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.USER,
            user_id=user_id,
            reference_currency=reference_currency,
        )

    def has_market_exceeded_limit(self, amount: decimal.Decimal, is_sell: bool, reference_currency: int) -> bool:
        """
        Checks if the market has exceeded its market limit.
        :param amount: The amount of the transaction.
        :param is_sell: Whether the transaction is a sell.
        :param reference_currency: The currency in which the amount is referenced.
        :return: True if the market has exceeded the limit, False otherwise.
        """
        return self._has_limit_exceeded(
            amount=amount,
            is_sell=is_sell,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
            reference_currency=reference_currency,
        )

    def _has_limit_exceeded(
        self,
        amount: decimal.Decimal,
        is_sell: bool,
        limit_type: int,
        reference_currency: int,
        user_id: Optional[int] = None,
    ) -> bool:
        """
        Internal helper method to check if a limit has been exceeded.
        :param amount: The amount of the transaction.
        :param is_sell: Whether the transaction is a sell.
        :param limit_type: The type of limit to check (user or entire market).
        :param user_id: The ID of the user (required for user limits).
        :param reference_currency: The currency in which the amount is referenced.
        :return: True if the limit has been exceeded, False otherwise.
        """
        # Retrieve the active limit
        limit = self.limits.filter(limit_type=limit_type, is_sell=is_sell, is_active=True).first()
        if not limit:
            return False

        market_strategy = self.get_market_limitation_strategy()(self, amount, is_sell, reference_currency)

        # Calculate the time threshold
        time_threshold = ir_now() - datetime.timedelta(hours=limit.interval)

        # Build the queryset for trades
        trades_queryset = ExchangeTrade.objects.filter(
            src_currency=self.base_currency,
            dst_currency=self.quote_currency,
            created_at__gt=time_threshold,
            status__in=[ExchangeTrade.STATUS.succeeded, ExchangeTrade.STATUS.unknown],
            is_sell=is_sell,
        )

        if limit_type == MarketLimitation.LIMIT_TYPE_CHOICES.USER:
            if user_id is None:
                raise ValueError('user_id must be provided for user limits.')
            trades_queryset = trades_queryset.filter(user_id=user_id)

        # Aggregate the total traded amount
        total_traded_amount = trades_queryset.aggregate(total_amount=Coalesce(Sum(market_strategy.amount_field), ZERO))[
            'total_amount'
        ]

        # Check if the limit is exceeded
        return (total_traded_amount + market_strategy.amount) > limit.max_amount

    def get_market_limitation_strategy(self):
        if self.base_currency == Currencies.usdt and self.quote_currency == Currencies.rls:
            return USDTRLSStrategyInLimitation
        return DefaultStrategyInLimitation


class MarketLimitation(models.Model):
    LIMIT_TYPE_CHOICES = Choices(
        (1, 'USER', 'User'),
        (2, 'ENTIRE', 'Entire Market'),
    )

    interval = models.PositiveSmallIntegerField(help_text='Interval in hours')
    max_amount = models.DecimalField(
        max_digits=BALANCE_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
    )
    market = models.ForeignKey(MarketStatus, on_delete=models.CASCADE, related_name='limits')
    is_active = models.BooleanField(default=True)
    is_sell = models.BooleanField()
    limit_type = models.PositiveSmallIntegerField(choices=LIMIT_TYPE_CHOICES)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('market', 'is_sell', 'limit_type'), name='market_is_sell_limit_type_unique_together'
            )
        ]


class MarketMakerTrade(models.Model):
    convert_id = models.CharField(max_length=255, db_index=True)
    quote_id = models.CharField(max_length=255, null=True)
    client_id = models.CharField(max_length=255, null=True, db_index=True)
    status = models.CharField(max_length=50, null=True)
    is_sell = models.BooleanField(null=True)
    base_currency = models.IntegerField(choices=Currencies, null=True)
    quote_currency = models.IntegerField(choices=Currencies, null=True)
    reference_currency = models.IntegerField(choices=Currencies, null=True)
    reference_currency_amount = models.DecimalField(
        max_digits=TRANSACTION_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, null=True
    )
    destination_currency_amount = models.DecimalField(
        max_digits=TRANSACTION_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, null=True
    )
    market_maker_created_at = models.DateTimeField(db_index=True, null=True)
    market_maker_response = models.JSONField(null=True)


class TradeDiff(models.Model):
    STATUS_CHOICES = Choices(
        (1, 'SOLVED', 'Solved'),
        (2, 'UNSOLVED', 'Unsolved'),
    )
    DISCREPANCY_TYPE = Choices(
        (1, 'SOURCE_CURRENCY_TYPE', 'مغایرت در نوع کوین مبدا'),
        (2, 'DESTINATION_CURRENCY_TYPE', 'مغایرت در نوع کوین مقصد'),
        (3, 'SOURCE_CURRENCY_AMOUNT', 'مغایرت در مقدار کوین مبدا'),
        (4, 'DESTINATION_CURRENCY_AMOUNT', 'مغایرت در مقدار کوین مقصد'),
        (5, 'TRADE_TYPE', 'مغایرت در نوع معامله'),
        (6, 'TRADE_STATUS', 'مغایرت در وضعیت انجام معامله'),
        (7, 'MISSING_TRADE_MARKET_MAKER', 'معامله ناموجود سمت بازارگردان'),
        (8, 'MISSING_TRADE_NOBITEX', 'معامله ناموجود سمت نوبیتکس'),
    )
    exchange_trade = models.ForeignKey(ExchangeTrade, on_delete=models.CASCADE, related_name='trade_diffs', null=True)
    market_maker_trade = models.ForeignKey(
        MarketMakerTrade, on_delete=models.CASCADE, related_name='trade_diffs', null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    discrepancy_type = models.SmallIntegerField(choices=DISCREPANCY_TYPE, null=True)
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=STATUS_CHOICES.UNSOLVED)


class SmallAssetConvert(models.Model):
    """This model keep small assets convert that will be converted to other assets batch by Exchange Trade"""

    STATUS = Choices(
        (0, 'created', 'ثبت شده'),
        (10, 'in_progress', 'در حال پردازش'),
        (20, 'succeeded', 'موفق'),
        (30, 'failed', 'ناموفق'),
    )

    WAITING_FOR_CONVERT_STATUSES: ClassVar = [STATUS.created, STATUS.failed]

    user = models.ForeignKey(User, verbose_name='کاربر', on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=ir_now, db_index=True)
    status = models.SmallIntegerField(choices=STATUS, default=STATUS.created)

    src_currency = models.IntegerField(choices=Currencies, verbose_name='ارز مبدا')
    dst_currency = models.IntegerField(choices=Currencies, verbose_name='ارز مقصد')

    src_amount = models.DecimalField(max_digits=TRANSACTION_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES)
    dst_amount = models.DecimalField(max_digits=TRANSACTION_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES)

    src_transaction = models.ForeignKey(
        Transaction,
        null=True,
        blank=True,
        related_name='+',
        on_delete=models.CASCADE,
    )
    dst_transaction = models.ForeignKey(
        Transaction,
        null=True,
        blank=True,
        related_name='+',
        on_delete=models.CASCADE,
    )
    system_src_transaction = models.ForeignKey(
        Transaction,
        null=True,
        blank=True,
        related_name='+',
        on_delete=models.CASCADE,
    )
    system_dst_transaction = models.ForeignKey(
        Transaction,
        null=True,
        blank=True,
        related_name='+',
        on_delete=models.CASCADE,
    )

    related_batch_trade = models.ForeignKey(
        ExchangeTrade,
        null=True,
        blank=True,
        related_name='+',
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = 'تبدیل دارایی اندک صرافی'
        verbose_name_plural = verbose_name
        indexes: ClassVar = [
            models.Index(fields=('src_currency', 'dst_currency', 'status')),
            models.Index(fields=('related_batch_trade', 'status')),
        ]
