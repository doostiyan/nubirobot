import datetime
from collections import defaultdict
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_UP, Decimal
from typing import List, Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Case, F, Q, Sum, When
from django.db.models.functions import Greatest

from exchange.accounts.models import Notification, User
from exchange.base.api import NobitexAPIError
from exchange.base.calendar import ir_now
from exchange.base.constants import MAX_PRECISION, ZERO
from exchange.base.decorators import cached_method
from exchange.base.helpers import batcher, stage_changes
from exchange.base.locker import Locker
from exchange.base.logging import metric_incr, report_exception
from exchange.base.models import AMOUNT_PRECISIONS_V2, Currencies, Settings, get_currency_codename
from exchange.base.money import money_is_zero
from exchange.features.utils import is_feature_enabled
from exchange.liquidator.errors import LiquidatorException
from exchange.liquidator.models import LiquidationRequest
from exchange.margin.constants import (
    LIQUIDATION_MARK_PRICE_GUARD_RATE,
    SETTLEMENT_ORDER_PRICE_MARK_PRICE_GUARD_RATE,
    SETTLEMENT_ORDER_PRICE_RANGE_RATE,
    USDT_SETTLEMENT_PRICE_RANGE_RATE,
)
from exchange.margin.models import (
    Position,
    PositionCollateralChange,
    PositionFee,
    PositionLiquidationRequest,
    PositionOrder,
)
from exchange.market.markprice import MarkPriceCalculator
from exchange.market.models import Market, Order
from exchange.pool.models import LiquidityPool
from exchange.usermanagement.block import BalanceBlockManager
from exchange.wallet.models import Wallet


class MarginManager:
    @classmethod
    def create_margin_order(
        cls,
        user: User,
        order_type: int,
        src_currency: int,
        dst_currency: int,
        amount: Decimal,
        price: Decimal,
        execution_type: int,
        channel: int,
        param1: Optional[Decimal] = None,
        pair: Optional[Order] = None,
        leverage: Decimal = Position.BASE_LEVERAGE,
        client_order_id: Optional[str] = None
    ) -> Order:
        market = Market.get_for(src_currency, dst_currency)
        cls._check_market(market, close_beta=not is_feature_enabled(user, 'new_coins'))

        pool = LiquidityPool.get_for(src_currency if order_type == Order.ORDER_TYPES.sell else dst_currency)
        cls._check_pool(pool, only_active=True, user=user)

        cls._check_leverage(leverage, market, user)

        if pair:
            return cls._add_oco_pair_margin_order(pair, market, pool, amount, price, execution_type, param1)
        return cls._add_single_margin_order(
            user, order_type, market, pool, amount, price, execution_type, channel, param1, leverage, client_order_id
        )

    @classmethod
    @transaction.atomic
    def _add_single_margin_order(
        cls,
        user: User,
        order_type: int,
        market: Market,
        pool: LiquidityPool,
        amount: Decimal,
        price: Decimal,
        execution_type: int,
        channel: int,
        param1: Optional[Decimal] = None,
        leverage: Decimal = Position.BASE_LEVERAGE,
        client_order_id: Optional[str] = None,
    ):
        collateral = cls.get_collateral(market, leverage, order_type, amount, price or param1 or ZERO)
        delegating_amount = amount if order_type == Order.ORDER_TYPES.sell else collateral * leverage
        cls._check_amount(delegating_amount, pool, user)
        wallet = Wallet.get_user_wallet(user, market.dst_currency, tp=Wallet.WALLET_TYPE.margin)
        cls._check_wallet(wallet, collateral)
        order = cls._create_order(
            user=user, market=market, order_type=order_type, amount=amount, price=price,
            execution_type=execution_type, channel=channel, param1=param1, allow_small=False,
            client_order_id=client_order_id
        )
        position = Position.objects.create(
            user=user,
            src_currency=market.src_currency,
            dst_currency=market.dst_currency,
            side=order_type,
            collateral=collateral,
            leverage=leverage,
        )
        position.orders.add(order, through_defaults={'blocked_collateral': collateral})
        wallet.block(collateral)
        return order

    @classmethod
    @transaction.atomic
    def _add_oco_pair_margin_order(
        cls,
        pair: Order,
        market: Market,
        pool: LiquidityPool,
        amount: Decimal,
        price: Decimal,
        execution_type: int,
        param1: Decimal,
    ):
        position = pair.position_set.first()
        collateral = cls.get_collateral(market, position.leverage, pair.order_type, amount, price or param1)
        if pair.is_buy:
            delegating_amount = collateral * position.leverage - pair.total_price
            cls._check_amount(delegating_amount, pool, pair.user)
            wallet = Wallet.get_user_wallet(pair.user, market.dst_currency, tp=Wallet.WALLET_TYPE.margin)
            cls._check_wallet(wallet, collateral - position.collateral)
        order = cls._create_order(
            user=pair.user, market=market, order_type=pair.order_type, amount=amount, price=price,
            execution_type=execution_type, channel=pair.channel, param1=param1, pair=pair, allow_small=False,
        )
        position.orders.add(order, through_defaults={'blocked_collateral': collateral})
        if pair.is_buy:
            wallet.block(collateral - position.collateral)
            position.collateral = collateral
            position.save(update_fields=('collateral',))
        return order

    @classmethod
    def create_position_close_order(
        cls,
        pid: int,
        amount: Decimal,
        price: Decimal,
        execution_type: int,
        channel: int,
        param1: Optional[Decimal] = None,
        pair: Optional[Order] = None,
        client_order_id: Optional[str] = None
    ) -> Order:
        with transaction.atomic():
            position = Position.objects.filter(id=pid, status__in=Position.STATUS_ONGOING).select_for_update().last()
            cls._check_market(
                position.market, close_beta=not is_feature_enabled(position.user, 'new_coins'), check_margin=False
            )
            total_price = (price or param1 or position.market.get_last_trade_price()) * amount
            if pair:
                total_price -= pair.total_price
            order_type = Order.ORDER_TYPES.buy if position.is_short else Order.ORDER_TYPES.sell
            allow_small = cls._check_position(position, ZERO if pair else amount, total_price)
            order = cls._create_order(
                user=position.user, market=position.market, order_type=order_type, amount=amount,
                price=price, execution_type=execution_type, channel=channel, param1=param1, pair=pair,
                allow_small=allow_small, client_order_id=client_order_id
            )
            position.orders.add(order, through_defaults={})
        return order

    @staticmethod
    def get_collateral(market: Market, leverage: Decimal, side: int, amount: Decimal, price: Decimal) -> Decimal:
        market_price = market.get_last_trade_price() or ZERO
        price = price.quantize(market.price_precision, rounding=ROUND_HALF_EVEN)
        amount = amount.quantize(market.amount_precision, rounding=ROUND_DOWN)
        if side == Position.SIDES.sell or not price:
            price = max(market_price, price)
        total_price = price * amount
        total_precision = max(market.price_precision * market.amount_precision, MAX_PRECISION)
        return (total_price / leverage).quantize(total_precision, rounding=ROUND_UP)

    @staticmethod
    def _check_market(
        market: Optional[Market],
        *,
        close_beta: bool = True,
        check_margin: bool = True,
        use_200_status_code: bool = True,
    ):
        status_code = 200 if use_200_status_code else 400
        if not market:
            raise NobitexAPIError('InvalidMarketPair', 'Market Validation Failed', status_code=status_code)

        if not market.is_active:
            raise NobitexAPIError('MarketClosed', 'Market Validation Failed', status_code=status_code)

        if check_margin and not market.allow_margin:
            raise NobitexAPIError('MarginClosed', 'Margin Trading Not Open', status_code=status_code)

        if (
            market.is_alpha and close_beta
        ):
            raise NobitexAPIError('MarketClosed', 'Market is currently closed!', status_code=status_code)

    @staticmethod
    def _check_pool(pool: Optional[LiquidityPool], only_active: bool = True, user: User = None):
        if not pool:
            raise NobitexAPIError('UnsupportedMarginSrc', 'Unsupported Margin Src Currency')

        if not pool.is_active and only_active:
            raise NobitexAPIError('MarginClosed', 'Margin Trading Not Open')

        if user and not pool.has_trader_access(user):
            raise NobitexAPIError('UnsupportedMarginSrc', 'Unsupported Margin Src Currency')

    @classmethod
    def _check_amount(cls, amount: Decimal, pool: LiquidityPool, user: User):
        if amount > pool.available_balance:
            raise NobitexAPIError('AmountUnavailable', 'Amount Unavailable')

        delegation_limit = cls.get_user_pool_delegation_limit(user, pool=pool, lock=True)
        if amount > delegation_limit:
            raise NobitexAPIError('ExceedDelegationLimit', 'Amount exceeds delegation limit')

    @classmethod
    def get_user_pool_delegation_limit(
        cls, user: User, pool: Optional[LiquidityPool] = None, currency: Optional[int] = None, *, lock: bool = False
    ) -> Decimal:
        """Limit of each user for opening positions

        Each user has a limit on delegation from each pool's capacity
        """
        if not pool and not currency:
            raise TypeError('You should pass either pool or src_currency')
        if not pool:
            pool = LiquidityPool.get_for(currency)
            cls._check_pool(pool=pool, user=user)
        if lock:
            Locker.require_lock(f'pool_{pool.currency}_delegation_limit', user.id)
        user_limit = pool.get_user_delegation_limit(user)
        used_limit = (
            Position.objects.filter(
                Q(src_currency=pool.currency, side=Position.SIDES.sell)
                | Q(dst_currency=pool.currency, side=Position.SIDES.buy),
                user=user,
                pnl__isnull=True,
            )
            .annotate(
                taken=Case(When(Q(side=Position.SIDES.buy), then=-F('earned_amount')), default=F('delegated_amount')),
            )
            .aggregate(used_amount=Sum(Greatest(F('taken'), ZERO)))
        )['used_amount'] or 0
        used_limit += BalanceBlockManager.get_margin_balance_in_order(pool.currency, user)
        return max(user_limit - used_limit, ZERO)

    @staticmethod
    def _check_wallet(wallet: Optional[Wallet], needed_balance: Decimal):
        if not wallet:
            raise NobitexAPIError('UnsupportedMarginDst', 'Unsupported Margin Dst Currency')

        if wallet.active_balance < needed_balance:
            raise NobitexAPIError('InsufficientBalance', 'Insufficient Balance')

    @staticmethod
    def _check_position(position: Position, amount: Decimal, total_price: Decimal) -> bool:
        position.set_delegated_amount()
        amount_left = position.liability - position.liability_in_order
        if amount > amount_left:
            raise NobitexAPIError('ExceedLiability', 'Amount Exceeds Liability')

        if position.is_short and total_price > position.total_asset - position.asset_in_order:
            raise NobitexAPIError('ExceedTotalAsset', 'Total Price Exceeds Position Total Asset')

        return amount == amount_left

    @classmethod
    def _check_leverage(cls, leverage: Decimal, market: Market, user: User):
        if leverage == Position.BASE_LEVERAGE:
            return

        if user.is_restricted('Leverage'):
            raise NobitexAPIError('LeverageUnavailable')

        if leverage > market.max_leverage:
            raise NobitexAPIError(
                'LeverageTooHigh', f'Max leverage for {market.symbol} is {market.max_leverage.normalize()}'
            )

        user_max_leverage = cls.get_user_max_leverage(user)
        if leverage > user_max_leverage:
            raise NobitexAPIError('LeverageTooHigh', f'Max leverage for user is {user_max_leverage}')

    @classmethod
    def get_user_max_leverage(cls, user) -> Decimal:
        leverages = cls._get_user_type_max_leverages()
        for user_type in sorted(leverages, reverse=True):
            if user.user_type >= user_type:
                return leverages[user_type]
        return Position.BASE_LEVERAGE

    @classmethod
    @cached_method
    def _get_user_type_max_leverages(cls):
        """Return max leverage for each user level

        Example:
            {44: Decimal('3'), 46: Decimal('5')}
        """
        user_level_key_map = {f'margin_max_leverage_{user_type}': user_type for user_type, _ in User.USER_TYPES}
        return {
            user_level_key_map[setting.key]: Decimal(setting.value) if setting.value else Position.BASE_LEVERAGE
            for setting in Settings.objects.filter(key__in=user_level_key_map)
        }

    @staticmethod
    def _create_order(**kwargs) -> Order:
        order, err = Order.create(**kwargs, is_margin=True, is_validated=True)
        if err:
            if err == 'LargeOrder':
                raise NobitexAPIError(err, 'Order value is temporarily limited to below 1,000,000,000.')
            if err == 'MarketExecutionTypeTemporaryClosed':
                msg = (
                    'در حال حاضر امکان ثبت سفارش سریع در این بازار وجود ندارد.'
                    ' لطفاً از سفارش گذاری با تعیین قیمت استفاده نمایید.'
                )
                raise NobitexAPIError(err, msg)
            raise NobitexAPIError(err, 'Order Validation Failed')
        return order

    @staticmethod
    def _release_position_collateral_on_order_cancel(position: Position, position_order: PositionOrder):
        """On margin order cancellation, releases unmatched part

        Call when position is locked only!
        """
        assert position_order.order.status == Order.STATUS.canceled
        if not position.collateral or not position_order.blocked_collateral:
            return
        position_order.refresh_from_db()
        order_fixed_collateral = (position_order.order.matched_total_price / position.leverage).quantize(
            MAX_PRECISION, rounding=ROUND_UP
        )
        released_collateral = min(
            max(position_order.blocked_collateral - order_fixed_collateral, ZERO), position.collateral
        )
        if not released_collateral:
            return
        position_order.blocked_collateral -= released_collateral
        position_order.save(update_fields=('blocked_collateral',))
        if position_order.order.pair_id:
            pair_position_order = PositionOrder.objects.select_related('order').get(
                order_id=position_order.order.pair_id,
            )
            collateral_diff = pair_position_order.blocked_collateral - position_order.blocked_collateral
            if collateral_diff > released_collateral:
                return
            if collateral_diff > 0:
                released_collateral -= collateral_diff

        position.collateral -= released_collateral
        position.save(update_fields=('collateral',))
        wallet = Wallet.get_user_wallet(position.user_id, position.dst_currency, tp=Wallet.WALLET_TYPE.margin)
        if position.pnl is None:  # i.e. position is not settled
            wallet.unblock(released_collateral)

    @staticmethod
    def _recalculate_position_fields(position):
        if position.pnl is not None:
            position.set_delegated_amount()  # to check double spend and report
            return
        with stage_changes(
            position,
            update_fields=(
                'delegated_amount',
                'earned_amount',
                'liquidation_price',
                'status',
                'opened_at',
                'closed_at',
                'freezed_at',
                'pnl',
                'pnl_transaction',
                'entry_price',
                'exit_price',
            ),
        ):
            position.set_delegated_amount()
            position.set_earned_amount()
            position.set_entry_price()
            position.set_exit_price()
            position.check_daily_fee()  # As a double check
            position.set_liquidation_price()
            position.set_status()
            position.set_opened_at()
            position.set_closed_at()
            position.set_freezed_at()
            position.set_pnl()

    @staticmethod
    def _bulk_recalculate_position_fields(positions):
        no_pnl_positions = []
        for position in positions:
            position.set_delegated_amount()
            if position.pnl is None:
                position.set_earned_amount()
                position.set_entry_price()
                position.set_exit_price()
                position.check_daily_fee()  # As a double check
                position.set_liquidation_price()
                position.set_status()
                position.set_opened_at()
                position.set_closed_at()
                position.set_freezed_at()
                position.set_pnl()
                no_pnl_positions.append(position)

        Position.objects.bulk_update(
            no_pnl_positions,
            fields=(
                'delegated_amount',
                'earned_amount',
                'liquidation_price',
                'status',
                'opened_at',
                'closed_at',
                'freezed_at',
                'pnl',
                'pnl_transaction',
                'entry_price',
                'exit_price',
            ),
        )
        return no_pnl_positions

    @classmethod
    def update_position_on_order_change(cls, position_order: PositionOrder):
        with transaction.atomic():
            position = Position.objects.select_for_update().filter(pk=position_order.position_id).first()
            if position_order.order.status == Order.STATUS.canceled:
                cls._release_position_collateral_on_order_cancel(position, position_order)
            cls._recalculate_position_fields(position)
        # TODO: remove on liquidator full launch
        if position.status not in Position.STATUS_ONGOING and position.pnl is None:
            cls.settle_position_in_system(position.id)

    @classmethod
    def bulk_update_positions_on_order_change(cls, position_orders: List[PositionOrder]):
        if not position_orders:
            return

        position_to_orders_map = defaultdict(list)
        for po in position_orders:
            position_to_orders_map[po.position_id].append(po)

        with transaction.atomic():
            # sorting by the `user_id` and `dst_currency` to avoid DEADLOCKS
            # in Wallet update statements. So, whenever we are updating wallets,
            # we are keeping the same order, so we won't face a DEADLOCK like this.
            # transaction A and B will run simultaneously:
            #   transaction A:
            #    UPDATE wallet_wallet SET balance = balance + %s WHERE id = 1
            #    UPDATE wallet_wallet SET balance = balance + %s WHERE id = 2
            #   transaction B:
            #    UPDATE wallet_wallet SET balance = balance + %s WHERE id = 2
            #    UPDATE wallet_wallet SET balance = balance + %s WHERE id = 1
            positions = (
                Position.objects.filter(pk__in=position_to_orders_map)
                .select_for_update(of=('self',), no_key=True)
                .order_by('user_id', 'dst_currency')
            )
            positions_map = positions.in_bulk()

            to_be_updated_positions = []
            for pos_id, pos_orders in position_to_orders_map.items():
                position = positions_map.get(pos_id)
                if not position:
                    continue

                for position_order in pos_orders:
                    if position_order.order.status == Order.STATUS.canceled:
                        cls._release_position_collateral_on_order_cancel(position, position_order)
                to_be_updated_positions.append(position)

            updated_positions = cls._bulk_recalculate_position_fields(to_be_updated_positions)
            positions_to_settle = []
            positions_with_updated_pnl_just_now = []
            for position in updated_positions:
                if position.pnl is None:
                    if position.status not in Position.STATUS_ONGOING:
                        positions_to_settle.append(position)
                else:
                    positions_with_updated_pnl_just_now.append(position)

        Position.bulk_notify_on_complete(positions_with_updated_pnl_just_now)
        cls.bulk_settle_positions_in_system([pos.pk for pos in positions_to_settle])

    @classmethod
    def update_position_on_liquidation_request_change(cls, position_liq_quest: PositionLiquidationRequest):
        with transaction.atomic():
            position = Position.objects.select_for_update().filter(pk=position_liq_quest.position_id).first()
            cls._recalculate_position_fields(position)
        if position_liq_quest.liquidation_request.is_open:
            return
        position_liq_quest.is_processed = True
        position_liq_quest.save(update_fields=('is_processed',))
        if position.pnl is None:
            MarginManager.settle_position_in_system(position.id)

    @staticmethod
    def get_position_collateral_range(position: Position) -> tuple:
        margin_ratio = position.margin_ratio

        if not margin_ratio or margin_ratio <= position.initial_margin_ratio:
            min_collateral = position.collateral
        else:
            min_collateral = max(
                position.collateral - position.total_asset * (1 - position.initial_margin_ratio / margin_ratio), ZERO
            ).quantize(AMOUNT_PRECISIONS_V2[position.dst_currency], rounding=ROUND_UP)

        wallet = Wallet.get_user_wallet(position.user, position.dst_currency, tp=Wallet.WALLET_TYPE.margin)
        max_collateral = position.collateral + max(wallet.active_balance, 0)

        return min_collateral, max_collateral

    @staticmethod
    def change_position_collateral(pid: int, new_collateral: Decimal) -> Position:
        new_collateral = new_collateral.quantize(MAX_PRECISION)
        with transaction.atomic():
            position = (
                Position.objects.select_for_update(of=('self',))
                .filter(pk=pid, status=Position.STATUS.open)
                .select_related('user')
                .first()
            )
            if not position:
                raise NobitexAPIError('InvalidPosition', 'Position not found')

            log = PositionCollateralChange(position=position)
            with stage_changes(position, update_fields=('collateral', 'liquidation_price', 'status', 'freezed_at')):
                wallet = Wallet.get_user_wallet(position.user, position.dst_currency, tp=Wallet.WALLET_TYPE.margin)
                collateral_change = new_collateral - position.collateral
                position.collateral = new_collateral

                if new_collateral < 0:  # Negativity recheck
                    raise NobitexAPIError('NegativeCollateral', 'Collateral cannot get negative')

                if collateral_change < 0:
                    margin_ratio = position.margin_ratio
                    if not margin_ratio:
                        raise NobitexAPIError('TryAgainLater', 'Collateral change is temporarily unavailable')

                    if margin_ratio < position.initial_margin_ratio:
                        raise NobitexAPIError(
                            'LowMarginRatio',
                            f'Margin ratio must be above {position.initial_margin_ratio} after collateral change'
                        )

                elif collateral_change > wallet.active_balance:
                    raise NobitexAPIError('InsufficientBalance', 'Insufficient margin active balance')

                wallet.block(collateral_change)
                position.set_liquidation_price()
                position.set_status()
                position.set_freezed_at()
            log.save()
        return position

    @staticmethod
    def _cancel_active_orders(position: Position):
        settlement_expiry_threshold = ir_now() - settings.MARGIN_SYSTEM_ORDERS_MAX_AGE
        to_cancel_orders = (
            position.orders.select_for_update()
            .filter(
                status__in=Order.OPEN_STATUSES,
            )
            .exclude(
                channel=Order.CHANNEL.system_margin,
                created_at__gt=settlement_expiry_threshold,
            )
            .order_by('created_at')
        )
        for order in to_cancel_orders:
            order.do_cancel()

    @staticmethod
    def _request_liquidation_to_liquidator(position: Position):
        pool = LiquidityPool.get_for(position.src_currency if position.is_short else position.dst_currency)
        try:
            liquidation_request = LiquidationRequest.create(
                user_id=pool.manager_id,
                src_currency=position.src_currency,
                dst_currency=position.dst_currency,
                side=LiquidationRequest.SIDES.buy if position.is_short else LiquidationRequest.SIDES.sell,
                amount=position.delegated_amount,
            )
            position.liquidation_requests.add(liquidation_request)
        except LiquidatorException as e:
            Notification.notify_admins(
                f'Cannot create liquidation request for position: #{position.id}\nReason: {e}',
                title=f'‼️Position - {position.market.symbol}',
                channel='pool',
            )

    @staticmethod
    def _place_order_in_market(position: Position):
        market_price = position.market.get_last_trade_price() or ZERO
        mark_price = MarkPriceCalculator.get_mark_price(position.src_currency, position.dst_currency)
        settlement_range_rate = (
            SETTLEMENT_ORDER_PRICE_RANGE_RATE
            if position.src_currency != Currencies.usdt
            else USDT_SETTLEMENT_PRICE_RANGE_RATE
        )
        price = market_price * (1 + settlement_range_rate if position.is_short else 1 - settlement_range_rate)
        if mark_price:
            price = (
                min(mark_price * (1 + SETTLEMENT_ORDER_PRICE_MARK_PRICE_GUARD_RATE), price)
                if position.is_short
                else max(mark_price * (1 - SETTLEMENT_ORDER_PRICE_MARK_PRICE_GUARD_RATE), price)
            )

        amount = position.liability
        max_total_price = settings.NOBITEX_OPTIONS['maxOrders']['default'][position.dst_currency] * Decimal('0.9')
        if amount * price > max_total_price:
            amount = (max_total_price / price).quantize(position.market.amount_precision, rounding=ROUND_DOWN)

        settlement_order, err = Order.create(
            user=position.user,
            market=position.market,
            order_type=Order.ORDER_TYPES.buy if position.is_short else Order.ORDER_TYPES.sell,
            execution_type=Order.EXECUTION_TYPES.limit,
            amount=amount,
            price=price,
            channel=Order.CHANNEL.system_margin,
            is_margin=True,
            is_validated=True,
            allow_small=True,
        )
        if err:
            Notification.notify_admins(
                f'Cannot place order to settle liquidated position: #{position.id}\nReason: {err}'
                f'\nPrice: [{price}]',
                title=f'‼️Position - {position.market.symbol}',
                channel='pool',
            )
        else:
            position.orders.add(settlement_order, through_defaults={})

    @classmethod
    def settle_position_in_system(cls, pid: int):
        with transaction.atomic():
            position = Position.objects.select_for_update(of=('self',)).filter(pk=pid).select_related('user').first()

            if position.status in Position.STATUS_ONGOING:
                return

            cls._cancel_active_orders(position)

            if any(order.is_active and order.is_placed_by_system for order in position.cached_orders) or any(
                liq_quest.is_open for liq_quest in position.cached_liquidation_requests
            ):
                return

            position.set_delegated_amount()
            if money_is_zero(position.liability):
                return

            if LiquidationRequest.is_market_enabled_in_liquidator(position.market):
                cls._request_liquidation_to_liquidator(position)
            else:
                cls._place_order_in_market(position)

    @classmethod
    @transaction.atomic
    def bulk_settle_positions_in_system(cls, position_ids: List[int]):
        from exchange.market.order_cancel import bulk_cancel_orders

        positions = Position.objects.filter(id__in=position_ids).exclude(status__in=Position.STATUS_ONGOING)

        settlement_expiry_threshold = ir_now() - settings.MARGIN_SYSTEM_ORDERS_MAX_AGE
        locked_positions = positions.select_for_update(of=('self',))

        order_ids_to_cancel = (
            Order.objects.filter(position__in=locked_positions, status__in=Order.OPEN_STATUSES)
            .exclude(channel=Order.CHANNEL.system_margin, created_at__gt=settlement_expiry_threshold)
            .select_for_update()
            .values_list('id', flat=True)
        )
        bulk_cancel_orders(order_ids_to_cancel)

        retuning_positions = []
        locked_positions = (
            positions.select_related('user')
            .prefetch_related('liquidation_requests', 'orders')
            .select_for_update(of=('self',))
        )
        for position in locked_positions:
            has_active_or_system_order = any(
                order.is_active and order.is_placed_by_system for order in position.orders.all()
            )
            has_open_liquidation_request = any(liq_req.is_open for liq_req in position.liquidation_requests.all())
            if has_active_or_system_order or has_open_liquidation_request:
                continue

            position.set_delegated_amount()
            if money_is_zero(position.liability):
                continue
            retuning_positions.append(position)

            if LiquidationRequest.is_market_enabled_in_liquidator(position.market):
                cls._request_liquidation_to_liquidator(position)
            else:
                cls._place_order_in_market(position)

        return retuning_positions

    @staticmethod
    def extend_position(pid: int, date: datetime.date):
        with transaction.atomic():
            position = Position.objects.select_for_update(of=('self',)).filter(pk=pid).select_related('user').first()
            if position.collateral < position.extension_fee_amount:
                position.status = Position.STATUS.expired
                position.set_freezed_at()
                position.save(update_fields=('status', 'freezed_at'))
            else:
                try:
                    PositionFee.objects.get_or_create(position=position, date=date)
                except (ValueError, AttributeError) as e:  # Shall never happen
                    report_exception()
                    Notification.notify_admins(
                        f'Cannot claim position fee: #{position.id}\nReason: {e}',
                        title=f'‼️Position - {position.market.symbol}',
                        channel='pool',
                    )

    @staticmethod
    def liquidate_positions(src_currency: int, dst_currency: int, min_price: Decimal, max_price: Decimal) -> int:
        """Liquidate positions with liquidation price below market price."""
        if not settings.MARGIN_ENABLED:
            return 0

        mark_price = MarkPriceCalculator.get_mark_price(src_currency, dst_currency)
        if mark_price:
            min_price = max(min_price, mark_price * (1 - LIQUIDATION_MARK_PRICE_GUARD_RATE))
            max_price = min(max_price, mark_price * (1 + LIQUIDATION_MARK_PRICE_GUARD_RATE))

        with transaction.atomic():
            Locker.require_lock('liquidate_positions', Market.get_for(src_currency, dst_currency).id)
            position_ids = (
                Position.objects.filter(
                    src_currency=src_currency,
                    dst_currency=dst_currency,
                    status=Position.STATUS.open,
                )
                .filter(
                    Q(side=Position.SIDES.sell, liquidation_price__lte=max_price)
                    | Q(side=Position.SIDES.buy, liquidation_price__gte=min_price),
                )
                .select_for_update(skip_locked=True)
                .values_list('id', flat=True)
            )

            stats = defaultdict(lambda: {'count': 0, 'sum': ZERO})

            for batch_position_ids in batcher(position_ids, batch_size=500, idempotent=True):
                updated_positions = Position.objects.raw(
                    '''UPDATE margin_position
                    SET status = %(liquidated_status)s, freezed_at=NOW()
                    WHERE id in %(position_ids)s
                    RETURNING id, src_currency, dst_currency, side, delegated_amount''',
                    params={
                        'liquidated_status': Position.STATUS.liquidated,
                        'position_ids': tuple(batch_position_ids),
                    },
                )

                for position in updated_positions:
                    stats[(position.src_currency, position.dst_currency, position.side)]['count'] += 1
                    stats[(position.src_currency, position.dst_currency, position.side)]['sum'] += position.liability

            # Update metrics
            for (src, dst, side), stat in stats.items():
                labels = (get_currency_codename(src), get_currency_codename(dst), Position.SIDES[side].lower())
                metric_incr(f'metric_margin_liquidated_positions_count', stat['count'], labels)
                metric_incr(f'metric_margin_liquidated_positions_sum', float(stat['sum']), labels)

            return sum(stat['count'] for stat in stats.values())
