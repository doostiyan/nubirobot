from decimal import Decimal, DecimalException
from typing import Optional

from django.db import transaction
from django.db.models import Prefetch

from exchange.accounts.models import Notification, User
from exchange.base.calendar import ir_now
from exchange.base.constants import MAX_PRECISION, ZERO
from exchange.base.decorators import ram_cache
from exchange.base.logging import metric_incr, report_exception
from exchange.base.models import Currencies
from exchange.liquidator.broker_apis import SettlementRequest
from exchange.liquidator.constants import (
    EXTERNAL_ORDER_USDT_VALUE_THRESHOLD,
    TOLERANCE_MARK_PRICE,
    TOLERANCE_ORDER_PRICE,
    USDT_TOLERANCE_ORDER_PRICE,
)
from exchange.liquidator.errors import BrokerAPIError4XX, DuplicatedOrderError, EmptyPrice, InsufficientBalance
from exchange.liquidator.models import Liquidation, LiquidationRequest
from exchange.market.marketmanager import MarketManager
from exchange.market.markprice import MarkPriceCalculator
from exchange.market.models import Market, Order
from exchange.wallet.estimator import PriceEstimator


class OrderCreator:
    prefix_id = str
    market_type: int

    @classmethod
    @transaction.atomic
    def process(cls, liquidation_id: int):
        """
        Processes a list of liquidation requests and creates liquidations and market orders for them.
        """
        liquidation = (
            Liquidation.objects.filter(id=liquidation_id, status=Liquidation.STATUS.new)
            .prefetch_related(
                Prefetch(
                    'liquidation_requests',
                    queryset=LiquidationRequest.objects.select_related('src_wallet').order_by('id'),
                ),
            )
            .select_for_update(skip_locked=True)
            .first()
        )
        if not liquidation:
            metric_incr('metric_liquidator_order_creator_liquidation_not_found')
            return -1

        try:
            order_id = cls.create_order(liquidation)
            if order_id:
                liquidation.created_at = ir_now()
                liquidation.status = Liquidation.STATUS.open
                liquidation.save(update_fields=('created_at', 'order', 'tracking_id', 'status', 'market_type'))

        except EmptyPrice:
            Notification.notify_admins(
                f'Cannot create order. liquidation: #{liquidation.pk} - type: {cls.market_type}\n'
                'Reason: price is empty',
                title=f'‼️Ordering - {liquidation.symbol}',
                channel='liquidator',
            )

    @classmethod
    def create_order(cls, liquidation: Liquidation) -> Optional[str]:
        pass


class InternalOrderCreator(OrderCreator):
    """
    Converts liquidation requests into liquidation and create market orders.

    Provides methods for processing liquidation requests, creating market orders,
    and handling related calculations.
    """

    prefix_id = '!liquidation_'
    market_type: int = Liquidation.MARKET_TYPES.internal

    @classmethod
    def create_order(cls, liquidation: Liquidation) -> Optional[str]:
        """
        Creates a market order based on a liquidation, price, and user.
        Returns an Order object if successful, otherwise None.

        Args:
            liquidation (Liquidation): The liquidation event.

        Returns:
            Optional[Order]: The created market order, or None if unsuccessful.
        """
        liquidation.market_type = cls.market_type
        liquidation.tracking_id = f'{cls.prefix_id}{liquidation.pk}'

        price = cls._get_order_price(
            market=liquidation.market,
            is_sell=liquidation.is_sell,
        )
        liquidation_request = liquidation.liquidation_requests.first()
        user = cls._get_order_user(liquidation_request)

        order, error = MarketManager.create_order(
            user=user,
            src_currency=liquidation.src_currency,
            dst_currency=liquidation.dst_currency,
            amount=cls._get_order_amount(liquidation, user),
            order_type=liquidation.side,
            execution_type=Order.EXECUTION_TYPES.limit,
            channel=Order.CHANNEL.system_liquidator,
            allow_small=True,
            price=price,
            client_order_id=liquidation.tracking_id,
        )
        if error:
            Notification.notify_admins(
                f'Cannot place order to settle liquidated liquidation: #{liquidation.pk}\nReason: {error}'
                f'\nPrice: [{price}]',
                title=f'‼️Ordering - {liquidation.symbol}',
                channel='liquidator',
            )
            return None

        liquidation.order = order
        return order.pk

    @staticmethod
    def _get_order_price(market: Market, *, is_sell: bool) -> Decimal:
        """
        Retrieves the last market price for a given market and adds a tolerance to it.

        Args:
            market (Market): The market to get the price for.
            is_sell (boolean): side of order
        Returns:
            Decimal: The last market price.
        """
        tolerance_price = (
            TOLERANCE_ORDER_PRICE if market.src_currency != Currencies.usdt else USDT_TOLERANCE_ORDER_PRICE
        )
        price = market.get_last_trade_price() * (1 - tolerance_price if is_sell else 1 + tolerance_price)
        mark_price = MarkPriceCalculator.get_mark_price(market.src_currency, market.dst_currency)
        if mark_price:
            price = (
                max(price, mark_price * (1 - TOLERANCE_MARK_PRICE))
                if is_sell
                else min(price, mark_price * (1 + TOLERANCE_MARK_PRICE))
            )
        if price == ZERO:
            raise EmptyPrice()
        return price

    @staticmethod
    def _get_order_amount(liquidation: Liquidation, user: User):
        if liquidation.is_sell:
            return liquidation.amount

        fee_rate = MarketManager.get_trade_fee(liquidation.market, user, amount=1)
        amount = liquidation.amount / (1 - fee_rate)

        return amount.quantize(MAX_PRECISION)

    @classmethod
    @ram_cache(timeout=10 * 60)
    def _get_order_user_cached(cls, user_id: int) -> User:
        return User.objects.get(pk=user_id)

    @classmethod
    def _get_order_user(cls, liquidation_request: LiquidationRequest) -> User:
        wallet = liquidation_request.src_wallet
        if wallet.user_id < 1000:
            return cls._get_order_user_cached(wallet.user_id)

        return wallet.user


class ExternalOrderCreator(OrderCreator):
    prefix_id = 'broker_id_'
    market_type = Liquidation.MARKET_TYPES.external

    @classmethod
    @transaction.atomic
    def create_order(cls, liquidation: Liquidation) -> Optional[str]:
        if not cls._check_value_threshold(liquidation):
            return InternalOrderCreator().create_order(liquidation)

        liquidation.market_type = cls.market_type
        liquidation.tracking_id = f'{cls.prefix_id}{liquidation.pk}'
        try:
            cls._check_wallet(liquidation)
            SettlementRequest().request(liquidation)

        except DuplicatedOrderError:
            pass

        except BrokerAPIError4XX:
            return InternalOrderCreator().create_order(liquidation)

        except InsufficientBalance:
            Notification.notify_admins(
                f'Cannot create order. liquidation: #{liquidation.pk} - type: {cls.market_type}\n'
                'Reason: Insufficient Balance',
                title=f'‼️Ordering - {liquidation.symbol}',
                channel='liquidator',
            )
            return None

        except EmptyPrice:
            raise

        except Exception:
            report_exception()

        return liquidation.tracking_id

    @staticmethod
    def _check_wallet(liquidation: Liquidation):
        if liquidation.primary_price == ZERO:
            raise EmptyPrice()
        liquidation_request: LiquidationRequest = liquidation.liquidation_requests.first()
        active_amount = (
            liquidation_request.src_wallet.active_balance
            if liquidation_request.is_sell
            else Decimal(liquidation_request.dst_wallet.active_balance / liquidation.primary_price)
        )
        if active_amount < liquidation.amount:
            raise InsufficientBalance()

    @staticmethod
    def _convert_rial_value_to_usdt_value(rial_value):
        buy_price, sell_price = PriceEstimator.get_price_range(Currencies.usdt, Currencies.rls)
        return rial_value / buy_price

    @classmethod
    def _check_value_threshold(cls, liquidation: Liquidation):
        value = liquidation.amount * liquidation.primary_price

        if liquidation.dst_currency == Currencies.rls:
            # value is in Rial and must be converted to USDT
            try:
                value = cls._convert_rial_value_to_usdt_value(value)
            except DecimalException:
                return True

        return value >= EXTERNAL_ORDER_USDT_VALUE_THRESHOLD
