import datetime
import json
from decimal import Decimal
from numbers import Number
from typing import List, Optional

import pytz
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core import serializers
from django.core.cache import cache
from django.db import models
from django.db.models import Case, Count, F, Max, Min, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Greatest, Least
from django.utils import timezone
from django.utils.functional import cached_property
from model_utils import Choices

from exchange.accounts.models import ReferralProgram, User
from exchange.base.calendar import get_earliest_time, get_latest_time, ir_tz
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.constants import MONETARY_DECIMAL_PLACES, ZERO
from exchange.base.decorators import cached_method, ram_cache
from exchange.base.fields import RoundedDecimalField
from exchange.base.formatting import get_currency_unit
from exchange.base.models import (
    AMOUNT_PRECISIONS,
    LAUNCHING_CURRENCIES,
    PRICE_PRECISIONS,
    RIAL,
    TETHER,
    VALID_MARKET_SYMBOLS,
    Currencies,
    Settings,
    get_currency_codename,
    get_market_symbol,
    parse_market_symbol,
)
from exchange.base.money import money_is_zero
from exchange.base.publisher import OrderPublishManager, private_order_publisher
from exchange.base.serializers import serialize_choices
from exchange.base.strings import _t
from exchange.market.constants import FEE_MAX_DIGITS, ORDER_MAX_DIGITS, SYSTEM_USERS_VIP_LEVEL, TOTAL_VOLUME_MAX_DIGITS
from exchange.market.exceptions import ParseMarketError
from exchange.wallet.models import Transaction, Wallet

ORDER_STATUS = Choices(
    (0, 'new', 'New'),
    (1, 'active', 'Active'),
    (2, 'done', 'Done'),
    (3, 'canceled', 'Canceled'),
    (4, 'inactive', 'Inactive'),
)


class Market(models.Model):
    src_currency = models.IntegerField(choices=Currencies, verbose_name='ارز مبدا')
    dst_currency = models.IntegerField(choices=Currencies, verbose_name='ارز مقصد')
    is_active = models.BooleanField(default=False, verbose_name='فعال؟')

    allow_margin = models.BooleanField(default=False, verbose_name='معامله تعهدی مجاز است؟')
    max_leverage = models.DecimalField(max_digits=2, decimal_places=1, default=1, verbose_name='اهرم بیشینه')

    class Meta:
        verbose_name = 'بازار'
        verbose_name_plural = verbose_name

    @cached_property
    def symbol(self):
        return get_market_symbol(self.src_currency, self.dst_currency, market='nobitex')

    @property
    def market_display(self):
        return '{}-{}'.format(
            get_currency_unit(self.src_currency, en=True),
            get_currency_unit(self.dst_currency, en=True),
        )

    @staticmethod
    @ram_cache(default=[])
    def get_temporal_alpha_markets():
        """Whether this market is alpha"""
        return Settings.get_cached_json('temporal_alpha_markets', default=[])

    @property
    def is_alpha(self):
        """ Whether this market is alpha """
        if self.symbol in self.get_temporal_alpha_markets():
            return True
        get_launch_date = CURRENCY_INFO[self.src_currency].get('launch_date') or pytz.utc.localize(
            datetime.datetime.max
        )
        return self.src_currency in LAUNCHING_CURRENCIES and timezone.now() < get_launch_date

    @cached_property
    def price_precision(self):
        return PRICE_PRECISIONS.get(self.symbol, Decimal('1E-8'))

    @cached_property
    def amount_precision(self):
        return AMOUNT_PRECISIONS.get(self.symbol, Decimal('1E-8'))

    def get_last_trade_price(self) -> Decimal:
        """Return the last trade price of this Nobitex market.

            Note: For Rial markets, while the symbol has IRT like BTCIRT, returned prices are in IRR.
        """
        return cache.get(f'market_{self.id}_last_price') or Decimal('0')

    @classmethod
    def get_rial_market_ids(cls):
        """ Return market IDs of IRT markets. Useful for filtering trades without
            needing to join with Order table. The result is cached in RAM of each
            process for faster access. """
        rial_markets = getattr(cls, '_RIAL_MARKETS', None)
        if rial_markets is None:
            rial_markets = [m.id for m in cls.objects.filter(dst_currency=RIAL)]
            cls._RIAL_MARKETS = rial_markets
        return rial_markets

    @classmethod
    def get_tether_market_ids(cls) -> List[int]:
        """ Return market IDs of USDT markets. Useful for filtering trades without
            needing to join with Order table. The result is cached in RAM of each
            process for faster access. """
        tether_markets = getattr(cls, '_tether_MARKETS', None)
        if tether_markets is None:
            tether_markets = [m.id for m in cls.objects.filter(dst_currency=TETHER)]
            cls._tether_MARKETS = tether_markets
        return tether_markets

    @classmethod
    @cached_method
    def get_for(cls, src, dst):
        """ Return market object for the given pair
        """
        try:
            return cls.objects.get(src_currency=src, dst_currency=dst)
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_cached(cls, market_id):
        """ Get Market object from cache by DB id
        """
        cache_key = 'object_market_{}'.format(market_id)
        market = cache.get(cache_key)
        if market is not None:
            return market
        market = cls.objects.get(id=market_id)
        cache.set(cache_key, market, 600)
        return market

    @classmethod
    def get_active_markets(cls):
        return cls.objects.filter(is_active=True)

    @classmethod
    def by_symbol(cls, symbol: str) -> Optional['Market']:
        """Return the Market object based on market symbol"""
        src, dst = parse_market_symbol(symbol)
        if src and dst:
            return cls.get_for(src, dst)


class Order(models.Model):
    """ Order to buy/sell a fund in a market """
    ORDER_TYPES = Choices(
        (1, 'sell', 'Sell'),
        (2, 'buy', 'Buy'),
    )
    EXECUTION_TYPES = Choices(
        (1, 'limit', 'Limit'),
        (2, 'market', 'Market'),
        (11, 'stop_limit', 'StopLimit'),
        (12, 'stop_market', 'StopMarket'),
    )
    TRADE_TYPES = Choices(
        (1, 'spot', 'Spot'),
        (2, 'margin', 'Margin'),
        (3, 'credit', 'Credit'),
        (4, 'debit', 'Debit'),
    )
    STATUS = ORDER_STATUS
    OPEN_STATUSES = (STATUS.new, STATUS.active, STATUS.inactive)
    CHANNEL = Choices(
        (0, 'unknown', 'Unknown'),
        (1, 'web', 'Web'),
        (2, 'web_fast', 'WebFast'),
        (3, 'web_convert', 'WebConvert'),
        (4, 'web_simple', 'WebSimple'),
        (11, 'android', 'Android'),
        (12, 'android_fast', 'AndroidFast'),
        (13, 'android_convert', 'AndroidConvert'),
        (14, 'android_simple', 'AndroidSimple'),
        (21, 'ios', 'iOS'),
        (23, 'ios_convert', 'iOSConvert'),
        (31, 'api', 'API'),
        (32, 'api_internal', 'APIInternal'),
        (33, 'api_convert', 'APIConvert'),
        (34, 'api_internal_old', 'APIInternalOld'),
        (41, 'web_v1', 'WebV1'),
        (42, 'web_v2', 'WebV2'),
        (51, 'system_margin', 'SystemMargin'),
        (52, 'system_block', 'SystemBlock'),
        (53, 'system_abc_liquidate', 'SystemABCLiquidate'),
        (54, 'system_liquidator', 'SystemLiquidator'),
        (61, 'locket', 'Locket'),
    )
    CHANNEL_SYSTEM_RANGE = (50, 60)

    DEFAULT_EXECUTION_TYPE = EXECUTION_TYPES.limit
    BASIC_EXECUTION_TYPES = [EXECUTION_TYPES.limit, EXECUTION_TYPES.market]
    STOP_EXECUTION_TYPES = [EXECUTION_TYPES.stop_limit, EXECUTION_TYPES.stop_market]
    MARKET_EXECUTION_TYPES = [EXECUTION_TYPES.market, EXECUTION_TYPES.stop_market]
    ALL_EXECUTION_TYPES = BASIC_EXECUTION_TYPES + STOP_EXECUTION_TYPES

    id = models.BigAutoField(primary_key=True, editable=False)

    # Details
    user = models.ForeignKey(User, verbose_name='کاربر', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='تاریخ ایجاد')
    src_currency = models.IntegerField(choices=Currencies, verbose_name='ارز مبدا')
    dst_currency = models.IntegerField(choices=Currencies, verbose_name='ارز مقصد')
    description = models.CharField(max_length=1000, blank=True, default='', verbose_name='توضیحات')
    channel = models.SmallIntegerField(choices=CHANNEL, null=True, blank=True, verbose_name='کانال مبدا')

    # Unique per User, only a-z A-Z 0-9 and - (dash)
    client_order_id = models.CharField(max_length=32, blank=True, null=True, verbose_name='شناسه سفارش کاربر')

    # Matching Mode
    order_type = models.IntegerField(choices=ORDER_TYPES, verbose_name='نوع')
    execution_type = models.IntegerField(choices=EXECUTION_TYPES, default=DEFAULT_EXECUTION_TYPE, verbose_name='دستور')
    trade_type = models.PositiveSmallIntegerField(
        choices=TRADE_TYPES, default=TRADE_TYPES.spot, verbose_name='نوع معامله'
    )

    # Parameters
    price = models.DecimalField(
        max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, verbose_name='قیمت واحد'
    )
    amount = models.DecimalField(
        max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, verbose_name='مقدار ارز'
    )
    param1 = models.DecimalField(
        max_digits=ORDER_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
        verbose_name='پارامتر یک',
        null=True,
        blank=True,
    )

    # Matching Details
    status = models.IntegerField(choices=STATUS, default=STATUS.new, db_index=True, verbose_name='وضعیت')
    matched_amount = models.DecimalField(
        max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO, verbose_name='مقدار مچ شده'
    )
    matched_total_price = models.DecimalField(
        max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO, verbose_name='ارزش مچ شده'
    )
    fee = models.DecimalField(
        max_digits=FEE_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO, verbose_name='کارمزد'
    )
    pair = models.OneToOneField(
        'self', on_delete=models.SET_NULL, related_name='+', null=True, blank=True, verbose_name='زوج سفارش'
    )

    class Meta:
        verbose_name = 'سفارش'
        verbose_name_plural = verbose_name
        # Also there are some additional partial indices on production DB:
        #  - market_actives (src_currency, dst_currency) WHERE status = 1
        #  - user_actives  (user_id) WHERE status = 1
        #  - user_actives3 (user_id) WHERE status IN (0, 1, 4)
        indexes = (
            models.Index(
                fields=('src_currency', 'dst_currency'),
            ),
            models.Index(
                fields=('src_currency', 'dst_currency', 'price'),
                condition=Q(status=1, order_type=1) & ~Q(execution_type__in=(2, 12)),
                name='orderbook_asks',
            ),
            models.Index(
                fields=('src_currency', 'dst_currency', '-price'),
                condition=Q(status=1, order_type=2) & ~Q(execution_type__in=(2, 12)),
                name='orderbook_bids',
            ),
            models.Index(
                fields=('src_currency', 'dst_currency'),
                condition=Q(status=1, execution_type__in=(2, 12)),
                name='market_execution_orders',
            ),
            models.Index(
                fields=('src_currency', 'dst_currency', 'order_type', 'param1'),
                condition=Q(status=4, execution_type__in=(11, 12)),
                name='inactive_stop_execution_orders',
            ),
        )
        constraints = (
            models.UniqueConstraint(
                fields=['user', 'client_order_id'],
                name='unique_user_client_order_id',
                condition=Q(status__in=[ORDER_STATUS.new, ORDER_STATUS.active, ORDER_STATUS.inactive])
            ),
        )

    def __str__(self):
        return 'Order#{}: {} ({}) {}'.format(self.pk, self.user.email, self.get_order_type_display(),
                                             self.market_display)

    @property
    def is_buy(self):
        return self.order_type == self.ORDER_TYPES.buy

    @property
    def is_sell(self):
        return self.order_type == self.ORDER_TYPES.sell

    @property
    def is_market(self):
        return self.execution_type in self.MARKET_EXECUTION_TYPES

    @property
    def is_active(self):
        return self.status == self.STATUS.active

    @property
    def is_closed(self):
        return self.status in (self.STATUS.done, self.STATUS.canceled)

    @property
    def blocks_balance(self):
        if self.pair_id:
            if self.order_type == self.ORDER_TYPES.buy:
                if self.execution_type == self.EXECUTION_TYPES.limit:
                    return self.matched_amount > 0
                return not self.is_closed
            return self.is_active
        return not self.is_closed

    @property
    def is_margin(self):
        return self.trade_type == self.TRADE_TYPES.margin

    @property
    def is_spot(self):
        return self.trade_type == self.TRADE_TYPES.spot

    @property
    def is_credit(self):
        return self.trade_type == self.TRADE_TYPES.credit

    @property
    def is_debit(self):
        return self.trade_type == self.TRADE_TYPES.debit

    @cached_property
    def leverage(self) -> Optional[Decimal]:
        """Get position leverage of a margin order"""
        return self.position_set.values_list('leverage', flat=True).first()

    @cached_property
    def side(self) -> Optional[int]:
        """Get position side of a margin order"""
        return self.position_set.values_list('side', flat=True).first()

    @property
    def is_placed_by_system(self):
        return self.channel and self.CHANNEL_SYSTEM_RANGE[0] < self.channel < self.CHANNEL_SYSTEM_RANGE[1]

    @property
    def total_price(self):
        from exchange.wallet import estimator

        if self.is_sell:
            if self.execution_type in Order.STOP_EXECUTION_TYPES:
                return max(self.param1, self.price) * self.amount

            buy_price, _ = estimator.PriceEstimator.get_price_range(self.src_currency, self.dst_currency)
            return max(buy_price, self.price) * self.amount
        return self.price * self.amount

    @property
    def unmatched_total_price(self):
        return self.price * self.unmatched_amount

    @property
    def net_matched_total_price(self):
        return self.matched_total_price - self.fee

    @property
    def is_matched(self):
        return self.unmatched_amount <= 0

    @property
    def is_partial(self):
        return self.matched_amount > 0 and not self.is_matched

    @property
    def unmatched_amount(self):
        return self.amount - self.matched_amount

    @property
    def is_trivial(self):
        return money_is_zero(self.unmatched_amount)

    @property
    def average_price(self):
        """ Effective order price: average price of the matchings done for this order
        """
        if money_is_zero(self.matched_amount):
            return Decimal('0')
        return self.matched_total_price / self.matched_amount

    @property
    def market_display(self):
        market = '{}-{}'.format(get_currency_unit(self.src_currency, en=True),
                                get_currency_unit(self.dst_currency, en=True))
        return market

    @property
    def selling_currency(self):
        return self.src_currency if self.is_sell else self.dst_currency

    def update_status(self, status, manual=False):
        """ Update status of order

            Note: Order invalidation
        """
        if manual and self.is_placed_by_system:
            return False
        is_valid_transition = False
        if status == self.STATUS.active and self.status == self.STATUS.new:
            is_valid_transition = True
        if status == self.STATUS.canceled and self.status in [
            self.STATUS.new, self.STATUS.active, self.STATUS.inactive
        ]:
            is_valid_transition = True
        if not is_valid_transition:
            return False

        self.status = status
        self.save(update_fields=['status'])

        last_trade = (
            OrderMatching.objects.filter(sell_order=self).order_by('id').last()
            if self.is_sell
            else OrderMatching.objects.filter(buy_order=self).order_by('id').last()
        )
        order_publish_manager = OrderPublishManager()
        order_publish_manager.add_order(self, last_trade, self.user.uid)
        order_publish_manager.publish()

        if status == self.STATUS.canceled and self.pair and not self.pair.matched_amount:
            self.pair.update_status(status, manual)
        return True

    def do_cancel(self, manual=False):
        return self.update_status(self.STATUS.canceled, manual=manual)

    def _get_providing_wallet(self, currency: int) -> Optional[Wallet]:
        if self.is_margin:
            from exchange.margin.models import Position
            from exchange.pool.models import LiquidityPool

            pool = LiquidityPool.get_for(self.src_currency if self.side == Position.SIDES.sell else self.dst_currency)
            if not pool:
                return None
            provider_id = pool.manager_id
        else:
            provider_id = self.user_id

        return Wallet.get_user_wallet(provider_id, currency, self.wallet_type)

    @cached_property
    def src_wallet(self) -> Optional[Wallet]:
        return self._get_providing_wallet(self.src_currency)

    @cached_property
    def dst_wallet(self) -> Optional[Wallet]:
        return self._get_providing_wallet(self.dst_currency)

    @classmethod
    def create(cls, *args, **kwargs):
        from .marketmanager import MarketManager
        return MarketManager.create_order(*args, **kwargs)

    @classmethod
    def get_all_market_orders(
        cls, src_currency, dst_currency, status=None, user=None,
        date_from=None, date_to=None, order_type=None, execution_type=None,
    ):
        orders = cls.objects.all()
        if src_currency:
            orders = orders.filter(src_currency=src_currency)
        if dst_currency:
            orders = orders.filter(dst_currency=dst_currency)
        if status:
            orders = orders.filter(status=status)
        if date_from:
            orders = orders.filter(created_at__gte=date_from)
        if date_to:
            orders = orders.filter(created_at__lt=date_to)
        if user:
            orders = orders.filter(user=user)
        if order_type:
            orders = orders.filter(order_type=order_type)
        if execution_type:
            orders = orders.filter(execution_type=execution_type)
        return orders

    @classmethod
    def get_active_market_orders(cls, src_currency, dst_currency, **kwargs):
        kwargs['status'] = cls.STATUS.active
        return cls.get_all_market_orders(src_currency, dst_currency, **kwargs)

    @property
    def wallet_type(self):

        if self.is_credit:
            wallet_type = Wallet.WALLET_TYPE.credit
        elif self.is_debit:
            wallet_type = Wallet.WALLET_TYPE.debit
        else:
            wallet_type = Wallet.WALLET_TYPE.spot
        return wallet_type


class OrderMatching(models.Model):
    """ Represents a trade in system, that is a matching of two orders

        * The market of this trade is not stored directly in object (which was unintentional and
           can be added to model if needed), and is defined to be the market of `self.sell_order`.
        * It is assumed that (src_currency, dst_currency) for sell and buy orders are exactly the same
           for any trade. Also orders cannot have same src_currency and dst_currency.
    """

    # General Fields
    created_at = models.DateTimeField(db_index=True)

    # Related Orders
    market = models.ForeignKey(Market, related_name='trades', on_delete=models.CASCADE, null=True)
    seller = models.ForeignKey(User, related_name='+', on_delete=models.CASCADE, null=True)
    buyer = models.ForeignKey(User, related_name='+', on_delete=models.CASCADE, null=True)
    sell_order = models.ForeignKey(Order, related_name='+', on_delete=models.CASCADE)
    buy_order = models.ForeignKey(Order, related_name='+', on_delete=models.CASCADE)

    # Related Transfer Transactions
    sell_deposit = models.ForeignKey(Transaction, related_name='+', null=True, blank=True, on_delete=models.CASCADE)
    sell_withdraw = models.ForeignKey(Transaction, related_name='+', null=True, blank=True, on_delete=models.CASCADE)
    buy_deposit = models.ForeignKey(Transaction, related_name='+', null=True, blank=True, on_delete=models.CASCADE)
    buy_withdraw = models.ForeignKey(Transaction, related_name='+', null=True, blank=True, on_delete=models.CASCADE)

    # Related Fee Transactions
    sell_fee = models.ForeignKey(Transaction, related_name='+', null=True, blank=True, on_delete=models.CASCADE)
    buy_fee = models.ForeignKey(Transaction, related_name='+', null=True, blank=True, on_delete=models.CASCADE)

    # Match Details
    is_seller_maker = models.BooleanField(default=False)
    matched_price = models.DecimalField(max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES)
    matched_amount = models.DecimalField(max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES)
    rial_value = models.DecimalField(
        max_digits=ORDER_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
        null=True,
        blank=True,
        verbose_name='ارزش ریالی',
    )
    sell_fee_amount = RoundedDecimalField(
        max_digits=FEE_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
        null=True,
        blank=True,
        help_text='market.dst_currency',
    )
    buy_fee_amount = RoundedDecimalField(
        max_digits=FEE_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
        null=True,
        blank=True,
        help_text='market.src_currency',
    )

    class Meta:
        verbose_name = 'معامله'
        verbose_name_plural = verbose_name
        unique_together = ['sell_order', 'buy_order']

    def __str__(self):
        return 'OrderMatching#{}'.format(self.pk)

    @property
    def tx_ids_cache_key(self):
        return f'trade_{self.id}_txids'

    @property
    def market_display(self):
        market = '{}-{}'.format(get_currency_unit(self.src_currency, en=True),
                                get_currency_unit(self.dst_currency, en=True))
        return market

    @property
    def is_market_cached(self):
        """ Whether the market field of this trade points to a loaded Market object """
        return OrderMatching.market.is_cached(self)

    @property
    def src_currency(self):
        if self.is_market_cached:
            return self.market.src_currency
        return self.sell_order.src_currency

    @property
    def dst_currency(self):
        if self.is_market_cached:
            return self.market.dst_currency
        return self.sell_order.dst_currency

    @property
    def symbol(self):
        return get_market_symbol(self.src_currency, self.dst_currency, market='nobitex')

    @property
    def matched_total_price(self):
        return self.matched_price * self.matched_amount

    @property
    def is_market_sell(self):
        return self.sell_order.created_at > self.buy_order.created_at

    @property
    def is_small(self):
        """ Whether this trade is smaller than standard minimum value of Binance (~10USDT) """
        dst = self.dst_currency
        value = self.matched_total_price
        if dst == Currencies.rls:
            return value < Decimal('200_000_0')
        if dst == Currencies.usdt:
            return value < Decimal('10')
        # TODO: BTC Market
        return False

    def get_sell_fee_amount(self):
        """Return the fee amount payed by this trade's seller."""
        if self.sell_fee_amount is not None:
            return self.sell_fee_amount
        if self.sell_fee:
            return self.sell_fee.amount
        return Decimal('0')

    def get_buy_fee_amount(self):
        """Return the fee amount payed by this trade's buyer."""
        if self.buy_fee_amount is not None:
            return self.buy_fee_amount
        if self.buy_fee:
            return self.buy_fee.amount
        return Decimal('0')

    @cached_property
    def trade_description(self):
        """Get trade description in human-readable format"""
        matched_amount_str = f'{self.matched_amount.quantize(self.market.amount_precision).normalize():,f}'
        matched_price_str = f'{self.matched_price.quantize(self.market.price_precision).normalize():,f}'
        return (
            f'{matched_amount_str} {_t(get_currency_codename(self.market.src_currency))}'
            f' به قیمت واحد {matched_price_str} {_t(get_currency_codename(self.market.dst_currency))}'
        )

    def create_sell_withdraw_transaction(self, *, commit=True, set_trade_time: bool = True):
        transaction = self.sell_order.src_wallet.create_transaction(
            tp='sell',
            amount=-self.matched_amount,
            created_at=self.created_at if set_trade_time else None,
            description='فروش ' + self.trade_description,
            ref_module=Transaction.REF_MODULES['TradeSellA'],
            ref_id=self.pk,
        )
        if transaction and commit:
            transaction.commit()
        return transaction

    def create_buy_withdraw_transaction(self, *, commit=True, set_trade_time: bool = True):
        transaction = self.buy_order.dst_wallet.create_transaction(
            tp='sell',
            amount=-self.matched_total_price,
            created_at=self.created_at if set_trade_time else None,
            description='خرید ' + self.trade_description,
            ref_module=Transaction.REF_MODULES['TradeSellB'],
            ref_id=self.pk,
        )
        if transaction and commit:
            transaction.commit()
        return transaction

    def create_sell_deposit_transaction(self, *, commit=True, set_trade_time: bool = True, wallet=None):
        wallet = wallet or self.sell_order.dst_wallet
        transaction = wallet.create_transaction(
            tp='buy',
            amount=self.matched_total_price - self.sell_fee_amount,
            created_at=self.created_at if set_trade_time else None,
            description='فروش ' + self.trade_description,
            ref_module=Transaction.REF_MODULES['TradeBuyA'],
            ref_id=self.id,
            allow_negative_balance=True,
        )
        if transaction and commit:
            transaction.commit(allow_negative_balance=True)
        return transaction

    def create_buy_deposit_transaction(self, *, commit=True, set_trade_time: bool = True, wallet=None):
        wallet = wallet or self.buy_order.src_wallet
        transaction = wallet.create_transaction(
            tp='buy',
            amount=self.matched_amount - self.buy_fee_amount,
            created_at=self.created_at if set_trade_time else None,
            description='خرید ' + self.trade_description,
            ref_module=Transaction.REF_MODULES['TradeBuyB'],
            ref_id=self.pk,
            allow_negative_balance=True,
        )
        if transaction and commit:
            transaction.commit(allow_negative_balance=True)
        return transaction

    @classmethod
    def get_trades(cls, market=None, user=None, date_from=None, date_to=None, just_rial=False):
        trades = cls.objects.all()
        if market:
            trades = trades.filter(market=market)
        if user:
            trades = trades.filter(Q(buyer=user) | Q(seller=user))
        if date_from:
            trades = trades.filter(created_at__gte=date_from)
        if date_to:
            trades = trades.filter(created_at__lte=date_to)
        if just_rial:
            trades = trades.filter(buy_order__dst_currency=RIAL)
        return trades


"""Archived"""
class MarketData(models.Model):
    src_currency = models.IntegerField(choices=Currencies)
    dst_currency = models.IntegerField(choices=Currencies)
    date = models.DateField(db_index=True)
    hour = models.IntegerField()
    open_price = models.DecimalField(max_digits=25, decimal_places=10, default=0)
    close_price = models.DecimalField(max_digits=25, decimal_places=10, default=0)
    low_price = models.DecimalField(max_digits=25, decimal_places=10, default=0)
    high_price = models.DecimalField(max_digits=25, decimal_places=10, default=0)
    trade_amount = models.DecimalField(max_digits=25, decimal_places=10, default=0)
    trade_total = models.DecimalField(max_digits=30, decimal_places=10, default=0)

    class Meta:
        verbose_name = 'Market Data'
        verbose_name_plural = verbose_name
        unique_together = ['src_currency', 'dst_currency', 'date', 'hour']


class MarketCandle(models.Model):
    RESOLUTIONS = Choices(
        (1, 'minute', 'Minute'),
        (2, 'hour', 'Hour'),
        (3, 'day', 'Day'),
    )

    market = models.ForeignKey(Market, on_delete=models.CASCADE)
    resolution = models.IntegerField(choices=RESOLUTIONS)
    start_time = models.DateTimeField(db_index=True)
    open_price = models.DecimalField(max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO)
    close_price = models.DecimalField(max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO)
    low_price = models.DecimalField(max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO)
    high_price = models.DecimalField(max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO)
    trade_amount = models.DecimalField(
        max_digits=TOTAL_VOLUME_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO
    )
    trade_total = models.DecimalField(
        max_digits=TOTAL_VOLUME_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO
    )
    price_lower_bound = models.DecimalField(
        max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, null=True, blank=True
    )
    price_upper_bound = models.DecimalField(
        max_digits=ORDER_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, null=True, blank=True
    )

    class Meta:
        unique_together = ('market', 'start_time', 'resolution')


    def get_change_percent(self, other: 'MarketCandle') -> float:
        if not other or money_is_zero(other.close_price):
            return 0
        change = (self.close_price - other.close_price) * 100 / other.close_price
        return round(float(change), 2)

    @cached_property
    def timestamp(self) -> int:
        return int(self.start_time.timestamp())

    @cached_property
    def duration(self) -> datetime.timedelta:
        return self.resolution_to_timedelta(self.resolution)

    @cached_property
    def end_time(self) -> datetime.datetime:
        return self.start_time + self.duration

    @cached_property
    def public_open_price(self) -> Decimal:
        return self._get_bounded_price(self.open_price)

    @cached_property
    def public_high_price(self) -> Decimal:
        return self._get_bounded_price(self.high_price)

    @cached_property
    def public_low_price(self) -> Decimal:
        return self._get_bounded_price(self.low_price)

    @cached_property
    def public_close_price(self) -> Decimal:
        return self._get_bounded_price(self.close_price)

    @classmethod
    def get_resolution_key(cls, resolution: int) -> Optional[str]:
        return serialize_choices(cls.RESOLUTIONS, resolution)

    def _get_bounded_price(self, price: Decimal) -> Decimal:
        if self.price_upper_bound:
            price = min(price, self.price_upper_bound)
        if self.price_lower_bound:
            price = max(price, self.price_lower_bound)
        return price

    @classmethod
    def resolution_to_timedelta(cls, resolution: int) -> datetime.timedelta:
        return timezone.timedelta(**{cls.get_resolution_key(resolution) + 's': 1})

    @classmethod
    def get_start_time(cls, dt: datetime.datetime, resolution: int) -> datetime.datetime:
        if resolution == cls.RESOLUTIONS.day:
            return get_earliest_time(dt.astimezone())
        kwargs = {'second': 0, 'microsecond': 0}
        if resolution > cls.RESOLUTIONS.minute:
            kwargs['minute'] = 0
        return dt.astimezone(ir_tz()).replace(**kwargs)

    @classmethod
    def get_end_time(cls, dt: datetime.datetime, resolution: int) -> datetime.datetime:
        if resolution == cls.RESOLUTIONS.day:
            return get_latest_time(dt.astimezone())
        kwargs = {'second': 59, 'microsecond': 999999}
        if resolution > cls.RESOLUTIONS.minute:
            kwargs['minute'] = 59
        return dt.astimezone(ir_tz()).replace(**kwargs)

    @classmethod
    def get_candle(cls, market: Market, resolution: int, dt: datetime.datetime) -> Optional['MarketCandle']:
        start_time = cls.get_start_time(dt, resolution)
        return cls.objects.filter(market=market, resolution=resolution, start_time=start_time).first()

    @classmethod
    def set_price_bounds(
        cls,
        market: Market,
        resolution: int,
        from_time: datetime.datetime,
        to_time: datetime.datetime,
        upper_bound: Optional[Number] = None,
        lower_bound: Optional[Number] = None,
        propagate: bool = True
    ) -> None:
        if upper_bound and lower_bound and lower_bound > upper_bound:
            return
        cls.objects.filter(
            market=market,
            start_time__gte=from_time,
            start_time__lt=to_time,
            resolution__lte=resolution,
        ).update(
            price_upper_bound=(
                Case(When(high_price__gt=upper_bound, then=upper_bound), default=None) if upper_bound else None
            ),
            price_lower_bound=(
                Case(When(low_price__lt=lower_bound, then=lower_bound), default=None) if lower_bound else None
            ),
        )
        if propagate:
            while resolution < cls.RESOLUTIONS.day:
                resolution += 1
                from_time = cls.get_start_time(from_time, resolution)
                cls.update_compound_candle_price_bounds(market, resolution, from_time, to_time)

    @classmethod
    def update_compound_candle_price_bounds(
        cls, market: Market, resolution: int, from_time: datetime.datetime, to_time: datetime.datetime
    ) -> None:
        base_candles = cls.objects.filter(
            market=market,
            resolution=resolution - 1,
            start_time__gte=OuterRef('start_time'),
            start_time__lt=OuterRef('start_time') + cls.resolution_to_timedelta(resolution),
            trade_amount__gt=0,
        ).values('market')
        cls.objects.filter(
            market=market,
            resolution=resolution,
            start_time__gte=from_time,
            start_time__lt=to_time,
        ).annotate(
            logical_upper_bound=Subquery(
                base_candles.annotate(ub=Max(Least('price_upper_bound', 'high_price'))).values('ub'),
                output_field=models.DecimalField()
            ),
            logical_lower_bound=Subquery(
                base_candles.annotate(lb=Min(Greatest('price_lower_bound', 'low_price'))).values('lb'),
                output_field=models.DecimalField()
            ),
        ).update(
            price_upper_bound=Case(
                When(high_price__gt=F('logical_upper_bound'), then=F('logical_upper_bound')), default=None
            ),
            price_lower_bound=Case(
                When(low_price__lt=F('logical_lower_bound'), then=F('logical_lower_bound')), default=None
            ),
        )


class SymbolInfo(models.Model):
    SYMBOL_TYPES = Choices(
        ('crypto-currency', 'crypto_currency', 'Crypto Currency'),
        ('flat-currency', 'flat_currency', 'Flat Currency'),
    )
    UDF_DATA_STATUS = Choices(
        'streaming',
        'endofday',
        'pulsed',
        'delayed_streaming',
    )
    src_currency = models.IntegerField(choices=Currencies)
    dst_currency = models.IntegerField(choices=Currencies)
    name = models.CharField(max_length=100)
    ticker = models.CharField(max_length=100)
    description = models.CharField(max_length=255, default="")
    type = models.CharField(max_length=20, choices=SYMBOL_TYPES)
    session = models.CharField(max_length=100, default="24x7")
    exchange = models.CharField(max_length=100, default="Nobitex")
    list_exchange = models.CharField(max_length=300, null=True, blank=True)
    timezone = models.CharField(max_length=40, default="Asia/Tehran")
    minmov = models.PositiveIntegerField(default=1)
    pricescale = models.PositiveIntegerField(default=100)
    minmove2 = models.PositiveIntegerField(default=0)
    fractional = models.BooleanField(default=False)
    has_intraday = models.BooleanField(default=True)
    supported_resolutions = models.CharField(max_length=255,
                                             default='["60"]')
    intraday_multipliers = models.CharField(max_length=255, default='["60"]')
    daily_multipliers = models.CharField(max_length=255, default='["1", "2", "3"]')
    has_seconds = models.BooleanField(default=False)
    seconds_multipliers = models.CharField(max_length=255, default='[]')
    has_daily = models.BooleanField(default=False)
    has_weekly_and_monthly = models.BooleanField(default=False)
    has_empty_bars = models.BooleanField(default=False)
    force_session_rebuild = models.BooleanField(default=True)
    has_no_volume = models.BooleanField(default=False)
    volume_precision = models.PositiveIntegerField(default=0)
    data_status = models.CharField(max_length=40, choices=UDF_DATA_STATUS)
    expired = models.BooleanField(default=False)
    expiration_date = models.DateField(null=True, blank=True)
    sector = models.CharField(max_length=100, default="Industrial")
    industry = models.CharField(max_length=100, default="Business Support Services")
    currency_code = models.CharField(max_length=100, default="﷼")

    class Meta:
        unique_together = ['name', 'exchange']

    def save(self, *args, update_fields=None, **kwargs):
        if not self.ticker:
            self.ticker = self.name
            if update_fields:
                update_fields = (*update_fields, 'ticker')

        super(SymbolInfo, self).save(*args, update_fields=update_fields, **kwargs)

    def set_array(self, key, data):
        setattr(self, key, json.dumps(data))

    def get_array(self, key):
        return json.loads(getattr(self, key))

    def to_json(self):
        symbol_json = json.loads(
            serializers.serialize("json", [self, ], use_natural_foreign_keys=True, use_natural_primary_keys=True))[0][
            'fields']
        symbol_json['supported_resolutions'] = self.get_array('supported_resolutions')
        symbol_json['intraday_multipliers'] = self.get_array('intraday_multipliers')
        symbol_json['seconds_multipliers'] = self.get_array('seconds_multipliers')
        symbol_json['daily_multipliers'] = self.get_array('daily_multipliers')
        symbol_json.pop('src_currency', None)
        symbol_json.pop('dst_currency', None)
        if not symbol_json.get('expiration_date'):  # Causes bug on TV v22.032
            symbol_json.pop('expiration_date', None)
        return symbol_json

    @classmethod
    def normalize(cls, symbol):
        symbol = symbol.split(':')[-1].upper()
        if symbol in VALID_MARKET_SYMBOLS:
            return symbol
        return None


class AutoTradingPermit(models.Model):
    FREQUENCY = Choices(
        (0, 'normal', 'Normal'),
        (1, 'fast', 'Fast'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    options = models.TextField(default='{}')
    values = models.TextField(default='{}')

    class Meta:
        verbose_name = 'دستور معامله‌ی خودکار'
        verbose_name_plural = verbose_name

    def __str__(self):
        return 'دستور معامله‌ی خودکار: ' + '، '.join(self.describe_permit(p) for p in self.permits)

    @property
    def permits(self):
        return self.get_options().get('permits') or []

    def get_options(self):
        return json.loads(self.options or '{}')

    def update_options(self, options, save=True):
        o = self.get_options()
        o.update(options)
        self.options = json.dumps(o)
        if save:
            self.save(update_fields=['options'])

    def get_values(self):
        return json.loads(self.values or '{}')

    def update_values(self, values, save=True):
        o = self.get_values()
        o.update(values)
        self.values = json.dumps(o)
        if save:
            self.save(update_fields=['values'])

    @classmethod
    def get_permit_usd(cls, permit):
        usd_value = permit.get('usd')
        order_type = permit.get('orderType')
        # Handle the special case of "system" value for USD
        if usd_value == 'system':
            system_usd = json.loads(Settings.get('usd_value'))
            usd_value = system_usd[order_type]
        if not usd_value:
            return Decimal('0')
        return Decimal(usd_value)

    @classmethod
    def describe_permit(cls, permit):
        t = {
            'sell': 'فروش',
            'buy': 'خرید',
            'btc': 'بیت‌کوین',
            'eth': 'اتریوم',
            'ltc': 'لایت‌کوین',
            'usdt': 'تتر',
            'xrp': 'ریپل',
            'all': 'همه',
            'simple': 'پیش‌فرض',
            'simple0': 'ساده',
            'step3': 'پله‌ای سه بخشی',
            'step30': 'پله‌ای سه بخشی ساده',
        }
        return '{}{} ارز {} با دلار {} تومان و چینش {}'.format(
            '' if permit.get('active') else '[غیرفعال] ',
            t.get(permit.get('orderType'), '?'),
            t.get(permit.get('srcCurrency'), '?'),
            'تتر' if permit.get('dstCurrency') == 'usdt' else round(int(cls.get_permit_usd(permit)) / 10),
            t.get(permit.get('plan'), '?'),
        )


##################
#  User Related  #
##################
class ReferralFee(models.Model):
    user = models.ForeignKey(User, related_name='referral_fees', on_delete=models.CASCADE)
    referred_user = models.ForeignKey(User, related_name='+', on_delete=models.CASCADE)
    referral_program = models.ForeignKey(ReferralProgram, null=True, blank=True, related_name='referral_fees',
                                         on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    amount = models.DecimalField(max_digits=FEE_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO)
    matching = models.ForeignKey(OrderMatching, related_name='referral_fees', on_delete=models.CASCADE)
    is_calculated = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'کارمزد ارجاع مشتری'
        verbose_name_plural = verbose_name

    @classmethod
    def get_referral_program_stats(cls, program, include_old_fees=False):
        """ Return statistics of trades related to the given referral code as a dict """
        stats = {
            'trades': 0,
            'profit': 0,
            'friendsTrades': 0,
            'friendsProfit': 0,
        }
        fees_filter = Q(referral_program=program)
        if include_old_fees:
            fees_filter |= Q(referral_program__isnull=True, user=program.user)
        fees = cls.objects.filter(fees_filter).annotate(is_giveback=Case(
            When(user=F('referred_user'), then=Value(True)),
            default=Value(False), output_field=models.BooleanField(),
        )).values('is_giveback').annotate(
            count=Count('*'),
            total=Sum('amount'),
        )
        for fee in fees:
            trades_count = fee['count'] or 0
            trades_total = int(fee['total'] or 0)
            if fee['is_giveback']:
                stats['friendsTrades'] += trades_count
                stats['friendsProfit'] += trades_total
            else:
                stats['trades'] += trades_count
                stats['profit'] += trades_total
        return stats


class UserTradeStatus(models.Model):
    user = models.OneToOneField(User, related_name='month_trades_status', on_delete=models.CASCADE)
    month_trades_count = models.IntegerField(default=0)
    month_trades_total = models.DecimalField(
        max_digits=TOTAL_VOLUME_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO
    )
    month_trades_total_trader = models.DecimalField(
        max_digits=30, decimal_places=10, default=0, verbose_name='مجموع معاملات پلن تریدر'
    )
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'آمار معاملات ماهانه کاربران'
        verbose_name_plural = verbose_name

    @property
    def net_month_trades(self):
        return self.month_trades_total

    @property
    def vip_level(self):
        """Return the user VIP level based on calculated monthly trade volume."""
        if self.user_id and self.user_id < 1000:
            return SYSTEM_USERS_VIP_LEVEL

        level_volumes = settings.NOBITEX_OPTIONS['tradingFees']['levelVolumes']
        levels_count = len(level_volumes)
        total_trade_volume = self.net_month_trades
        i = 1
        while i < levels_count:
            if total_trade_volume < level_volumes[i]:
                break
            i += 1
        return i - 1


class UserManualTransaction(models.Model):
    TRANSACTION_TYPES = Choices(
        (1, 'sell', 'Sell'),
        (2, 'buy', 'Buy'),
    )

    user = models.ForeignKey(User, related_name='manual_transactions', on_delete=models.CASCADE)
    transaction_type = models.IntegerField(choices=TRANSACTION_TYPES, verbose_name='نوع تراکنش')
    market = models.ForeignKey(Market, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=25, decimal_places=10, verbose_name='ارزش')
    amount = models.DecimalField(max_digits=25, decimal_places=10, verbose_name='مقدار')
    created_at = models.DateTimeField(db_index=True, verbose_name='تاریخ')
    description = models.TextField(verbose_name='توضیحات')

    class Meta:
        verbose_name = 'تراکنش دستی کاربر'
        verbose_name_plural = 'تراکنش‌های دستی کاربر'

    @classmethod
    def get_transactions(cls, market=None, user=None, date_from=None, date_to=None):
        transactions = cls.objects.all()
        if market:
            transactions = transactions.filter(market=market)
        if user:
            transactions = transactions.filter(user=user)
        if date_from:
            transactions = transactions.filter(created_at__gte=date_from)
        if date_to:
            transactions = transactions.filter(created_at__lte=date_to)
        return transactions


class UserMarketsPreferences(models.Model):
    user = models.OneToOneField(User, related_name='market_preferences', on_delete=models.CASCADE)
    favorite_markets = models.TextField(blank=True, null=True)

    @staticmethod
    def _get_cleaned_favorite_market(favorite_market):
        if not favorite_market:
            raise ValueError
        src, _ = parse_market_symbol(favorite_market)
        if not src:
            raise ParseMarketError(favorite_market)
        return favorite_market

    @classmethod
    def get_favorite_markets(cls, user: User) -> str:
        try:
            user_pref = cls.objects.get(user=user)
            return user_pref.favorite_markets
        except cls.DoesNotExist:
            return '[]'

    @classmethod
    def set_favorite_market(cls, user: User, market: str) -> List[str]:
        _market_list = []
        if "," in market:
            for fav_market in market.split(","):
                _market_list.append(cls._get_cleaned_favorite_market(fav_market.strip()))
        else:
            _market_list.append(cls._get_cleaned_favorite_market(market))
        try:
            user_pref = cls.objects.select_for_update().get(user=user)
            favorite_markets = json.loads(user_pref.favorite_markets)
            for _market in _market_list:
                if not favorite_markets.count(_market):
                    favorite_markets.append(_market)
            user_pref.favorite_markets = json.dumps(favorite_markets)
            user_pref.save(
                update_fields=[
                    'favorite_markets',
                ]
            )
        except cls.DoesNotExist:
            favorite_markets = json.dumps(_market_list)
            # We create_or_update instead of simple create as the object may be created due to concurrent call to this
            # API. If such happens, we simply ignore previous request and override it here.
            user_pref, _ = cls.objects.update_or_create(user=user, favorite_markets=favorite_markets)

        return json.loads(user_pref.favorite_markets)

    @classmethod
    def remove_favorite_market(cls, user: User, market: str = '') -> List[str]:
        try:
            user_pref = cls.objects.select_for_update().get(user=user)
            if market and market.lower() != 'all':
                _market = cls._get_cleaned_favorite_market(market)
                favorite_markets = json.loads(user_pref.favorite_markets)
                if favorite_markets.count(_market):
                    favorite_markets.remove(_market)
                    user_pref.favorite_markets = json.dumps(favorite_markets)
                    user_pref.save(update_fields=['favorite_markets', ])
            elif market and market.lower() == 'all':
                user_pref.favorite_markets = json.dumps([])
                user_pref.save(update_fields=['favorite_markets', ])
            else:
                raise ValueError

            return json.loads(user_pref.favorite_markets)
        except cls.DoesNotExist:
            return []


class FeeTransactionTradeList(models.Model):
    transaction = models.ForeignKey(to=Transaction, null=True, blank=True, on_delete=models.CASCADE)
    trades = ArrayField(models.IntegerField(), blank=True, default=list)
    currency = models.IntegerField(choices=Currencies)
    from_datetime = models.DateTimeField(null=False, blank=True)
    to_datetime = models.DateTimeField(null=False, blank=True)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)
