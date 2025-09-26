from decimal import ROUND_DOWN, Decimal
from typing import List, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils.functional import cached_property
from model_utils import Choices

from exchange.base.constants import ZERO
from exchange.base.models import AMOUNT_PRECISIONS_V2, Currencies, get_market_symbol
from exchange.liquidator.errors import MarketMakerUserNotFoundError
from exchange.liquidator.models.liquidation_request import LiquidationRequest
from exchange.market.models import Market, Order

User = get_user_model()


class Liquidation(models.Model):
    SIDES = Order.ORDER_TYPES
    STATUS = Choices(
        (0, 'new', 'New'),
        (1, 'open', 'Open'),
        (2, 'ready_to_share', 'Ready to share'),
        (3, 'done', 'Done'),
        (4, 'overstock', 'Overstock'),
    )
    ACTIVE_STATUSES = (STATUS.new, STATUS.open, STATUS.ready_to_share)

    MARKET_TYPES = Choices(
        (1, 'internal', 'Internal'),
        (2, 'external', 'External'),
    )

    src_currency = models.IntegerField(choices=Currencies, verbose_name='ارز مبدا')
    dst_currency = models.IntegerField(choices=Currencies.subset('rls', 'usdt'), verbose_name='ارز مقصد')
    side = models.SmallIntegerField(choices=SIDES, verbose_name='جهت')
    amount = models.DecimalField(max_digits=30, decimal_places=10, verbose_name='مقدار', default=ZERO)
    status = models.SmallIntegerField(choices=STATUS, default=STATUS.new, verbose_name='وضعیت')
    market_type = models.SmallIntegerField(
        choices=MARKET_TYPES, default=MARKET_TYPES.internal, verbose_name='بازار سفارش گذاری'
    )
    primary_price = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        verbose_name='قیمت اولیه',
        default=ZERO,
    )
    filled_amount = models.DecimalField(max_digits=30, decimal_places=10, verbose_name='مقدار پر شده', default=ZERO)
    filled_total_price = models.DecimalField(max_digits=30, decimal_places=10, verbose_name='ارزش پر شده', default=ZERO)
    paid_amount = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        verbose_name='مقدار پرداخت شده',
        default=ZERO,
    )
    paid_total_price = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        verbose_name='ارزش پرداخت شده',
        default=ZERO,
    )
    created_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, editable=False, verbose_name='تاریخ تغییر')
    tracking_id = models.CharField(
        max_length=32, null=True, blank=True, verbose_name='کد پیگیری سفارش لیکویید', unique=True
    )
    order = models.OneToOneField(Order, on_delete=models.SET_NULL, null=True, blank=True)
    liquidation_requests = models.ManyToManyField(
        LiquidationRequest,
        related_name='liquidations',
        verbose_name='درخواست‌های لیکویید',
        through='LiquidationRequestLiquidationAssociation',
    )

    class Meta:
        verbose_name = 'تسویه'
        verbose_name_plural = 'تسویه‌ها'
        indexes = (
            models.Index(
                fields=('status', 'created_at'),
                name='status_created_at_liqs',
            ),
        )

    @property
    def price(self) -> Decimal:
        if not self.filled_amount:
            return ZERO
        return (self.filled_total_price / self.filled_amount).quantize(
            AMOUNT_PRECISIONS_V2[self.src_currency],
            ROUND_DOWN,
        )

    @property
    def is_sell(self) -> bool:
        return self.side == Order.ORDER_TYPES.sell

    @property
    def symbol(self) -> Market:
        return get_market_symbol(self.src_currency, self.dst_currency)

    @cached_property
    def market(self) -> Market:
        return Market.get_for(self.src_currency, self.dst_currency)

    @property
    def unfilled_amount(self) -> Decimal:
        return self.amount - self.filled_amount

    @property
    def unshared_amount(self) -> Decimal:
        return self.filled_amount - self.paid_amount

    @property
    def unshared_total_price(self) -> Decimal:
        return self.filled_total_price - self.paid_total_price

    @classmethod
    @transaction.atomic
    def create(
        cls,
        liquidation_requests: List[LiquidationRequest],
        amount: Decimal,
        market_type: int,
        primary_price: Decimal,
    ) -> Optional['Liquidation']:
        if not liquidation_requests:
            return None
        liquidation = cls.objects.create(
            src_currency=liquidation_requests[0].src_currency,
            dst_currency=liquidation_requests[0].dst_currency,
            side=liquidation_requests[0].side,
            amount=amount,
            market_type=market_type,
            primary_price=primary_price,
        )
        liquidation.liquidation_requests.add(*liquidation_requests)
        return liquidation

    @staticmethod
    def get_marketmaker_user():
        try:
            user = User.objects.get(username=settings.EXTERNAL_LIQUIDATION_MARKETMAKER_USERNAME)
        except User.DoesNotExist:
            raise MarketMakerUserNotFoundError

        return user


class LiquidationRequestLiquidationAssociation(models.Model):
    liquidation_request = models.ForeignKey(
        'LiquidationRequest',
        on_delete=models.CASCADE,
        related_name='liquidation_associations',
    )
    liquidation = models.ForeignKey(
        Liquidation, on_delete=models.CASCADE, related_name='liquidation_request_associations'
    )
    amount = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        default=ZERO,
    )
    total_price = models.DecimalField(
        max_digits=30,
        decimal_places=10,
        default=ZERO,
    )

    class Meta:
        unique_together = ('liquidation_request', 'liquidation')
