import datetime
import json
from collections import defaultdict
from datetime import timedelta
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal
from typing import Dict, Iterable, List, Optional, TypedDict, Union

import pytz
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Count, Min, Q, QuerySet, Sum
from django.utils.timezone import now

from exchange.accounts.models import Notification, UserPlan, UserReferral
from exchange.accounts.userstats import UserStatsManager
from exchange.base.calendar import ir_now
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.constants import MAX_PRECISION
from exchange.base.decorators import measure_time_cm
from exchange.base.formatting import f_m
from exchange.base.helpers import batcher, get_dollar_buy_rate
from exchange.base.logging import log_event, metric_incr, report_exception
from exchange.base.models import (
    AMOUNT_PRECISIONS,
    BUY_PROMOTION_CURRENCIES,
    CURRENCY_CODENAMES,
    LAUNCHING_CURRENCIES,
    PRICE_PRECISIONS,
    Currencies,
    Settings,
)
from exchange.base.money import money_is_zero
from exchange.base.parsers import parse_utc_timestamp_ms
from exchange.base.publisher import (
    OrderPublishManager,
    private_order_publisher,
    private_trade_publisher,
    trades_publisher,
)
from exchange.base.serializers import serialize, serialize_decimal, serialize_timestamp
from exchange.base.settings import NobitexSettings
from exchange.base.strings import _t
from exchange.market.constants import MARKET_ORDER_MAX_PRICE_DIFF
from exchange.market.markprice import MarkPriceCalculator
from exchange.market.models import Market, Order, OrderMatching, ReferralFee, UserTradeStatus
from exchange.market.ws_serializers import serialize_trade_for_user
from exchange.wallet.estimator import PriceEstimator
from exchange.wallet.models import Wallet
from exchange.web_engage.events import OrderMatchedWebEngageEvent


class UserTradesData(TypedDict):
    month_trades_total: int
    month_trades_count: int


class MarketManager:
    @classmethod
    def get_market_promotion_end_date(cls, src_currency: int, dst_currency: int) -> datetime.datetime:  # noqa: ARG003
        """Return the end of promotion period for the market, defaulting to 3 days after launch."""
        min_date_localize = pytz.utc.localize(datetime.datetime.min)
        currency_info = CURRENCY_INFO.get(src_currency)
        if not currency_info:
            return min_date_localize
        promoted_date = currency_info.get('promote_date')
        if promoted_date:
            return promoted_date
        return (currency_info.get('launch_date') or min_date_localize) + datetime.timedelta(days=3)

    @classmethod
    def is_market_in_promotion(cls, src_currency: int, dst_currency: int, *, is_buy=False, nw=None) -> bool:
        """Check if the given coin/pair is in promotion and has zero fee."""
        nw = nw or now()
        promoted_date = cls.get_market_promotion_end_date(src_currency, dst_currency)
        if src_currency in LAUNCHING_CURRENCIES and nw < promoted_date:
            return True
        if src_currency in BUY_PROMOTION_CURRENCIES and is_buy and nw < promoted_date:
            return True
        return False

    @classmethod
    def get_trade_fee(cls, market, user=None, amount=None, is_maker=False, is_buy=False):
        """ Return the fee amount for a trade based on global settings, user options, and any applicable
            discount or promotion. The fee rate is determined from the UserStatsManager::get_user_fee
            and this method only adjusts that rate by market and trade parameters.
            # TODO: round fees to the meaningful digit for each currency
        """
        # Note: Matcher assumes and reimplements functionality of this method, so only change/mock this
        # code if you are sure the change is also applied in the matcher.
        if cls.is_market_in_promotion(market.src_currency, market.dst_currency, is_buy=is_buy):
            return Decimal('0')
        return UserStatsManager.get_user_fee(
            user, amount=amount, is_maker=is_maker,
            is_usdt=market.dst_currency == Currencies.usdt,
        )

    @classmethod
    def get_global_market_price(cls, market, is_sell):
        """ Return the global standard price for this market based on Binance
            market price and USDT exchange rate, or zero if data is unavailable.
        """
        price = NobitexSettings.get_binance_price(market.src_currency, default=Decimal('0'))
        if market.dst_currency == Currencies.rls:
            usd_value = Settings.get_dict('usd_value')
            # We use USDT sell value for buy market orders, because buy orders
            #  will match with sell side of the orderbook. So the Reversed order
            #  in the following line is intentional.
            price = price * usd_value.get('buy' if is_sell else 'sell', 0)
        return price

    @classmethod
    def detect_order_channel(cls, ua, is_convert=False):
        """Find order client type (channel) based on user agent of request."""
        ua = ua or ''
        if not ua or ua == '-':
            ua = 'TraderBot/NoUA'
        slash_ind = ua.find('/')
        if slash_ind >= 0:
            category = ua[:slash_ind]
        else:
            category = ''
        # Type
        tp_offset = 0
        if is_convert:
            tp_offset = 2
        # Detect channel base on category
        if category == 'Android':
            return Order.CHANNEL.android + tp_offset
        if category == 'iOSApp':
            return Order.CHANNEL.ios + tp_offset
        if category == 'TraderBot' and ua.startswith('TraderBot/Nobitex'):
            return Order.CHANNEL.api_internal
        if category.lower() in ['traderbot', 'python-requests', 'restsharp', 'guzzlehttp', 'python', 'axios']:
            return Order.CHANNEL.api + tp_offset
        if category == 'Mozilla':
            return Order.CHANNEL.web + tp_offset
        if category == 'LocketWallet':
            return Order.CHANNEL.locket
        return Order.CHANNEL.unknown

    @classmethod
    def get_last_trade_data(cls, market_id: int) -> tuple:
        """
        get last trade price and date from redis
        Args:
            market_id(int)
        Return:
        last price, last trade datetime
        """
        keys = (f'market_{market_id}_last_price', f'market_{market_id}_last_trade')
        trade_data = cache.get_many(keys=keys)
        return trade_data.get(keys[0]), trade_data.get(keys[1])

    @classmethod
    def create_order(
        cls,
        user=None,
        order_type=None,
        market=None,
        src_currency=None,
        dst_currency=None,
        execution_type=None,
        amount=None,
        price=None,
        param1=None,
        channel=None,
        description='',
        pair=None,
        is_margin=False,
        is_validated=False,
        allow_small=False,
        client_order_id=None,
        is_credit=False,
        is_debit=False,
    ):
        """Create an order. To place an order use this method that handles the validation and activation
        of the order, and never create Order objects by any means other than this method.
        Note: Order invalidation
        """
        # Parameter validation
        if market:
            src_currency = market.src_currency
            dst_currency = market.dst_currency
        else:
            market = Market.get_for(src_currency, dst_currency)
        if not market:
            return None, 'InvalidMarketPair'
        if not market.is_active:
            return None, 'MarketClosed'
        if order_type not in [Order.ORDER_TYPES.buy, Order.ORDER_TYPES.sell]:
            return None, 'InvalidOrderType'
        execution_type = execution_type or Order.DEFAULT_EXECUTION_TYPE
        if execution_type not in Order.ALL_EXECUTION_TYPES:
            return None, 'InvalidExecutionType'
        if execution_type == Order.EXECUTION_TYPES.market and market.symbol in Settings.get_list(
            'market_execution_disabled_market_list'
        ):
            return None, 'MarketExecutionTypeTemporaryClosed'

        if is_margin:
            trade_type = Order.TRADE_TYPES.margin
        elif is_credit:
            trade_type = Order.TRADE_TYPES.credit
        elif is_debit:
            trade_type = Order.TRADE_TYPES.debit
        else:
            trade_type = Order.TRADE_TYPES.spot

        # Useful variables
        market_symbol = market.symbol
        is_sell = order_type == Order.ORDER_TYPES.sell

        # Set price for all market orders
        # TODO: Also disallow market orders with very bad price
        if execution_type == Order.EXECUTION_TYPES.market:
            metric_incr('metric_market_order', labels=('price0' if not price else 'price1',))
            buy_price, sell_price = PriceEstimator.get_price_range(src_currency, dst_currency)
            if not price:
                price = buy_price if is_sell else sell_price
            elif buy_price and sell_price:
                allowed_change = MARKET_ORDER_MAX_PRICE_DIFF / 2
                has_unexpected_price = (
                    price > buy_price * (1 + allowed_change) if is_sell else price < sell_price * (1 - allowed_change)
                )
                if has_unexpected_price:
                    return None, 'UnexpectedMarketPrice'

        elif execution_type == Order.EXECUTION_TYPES.stop_market and not price:
            price = param1

        # Price and amount normalization
        if price:
            price = price.quantize(PRICE_PRECISIONS[market_symbol], rounding=ROUND_HALF_EVEN)
        if amount and not allow_small:
            amount = amount.quantize(AMOUNT_PRECISIONS[market_symbol], rounding=ROUND_DOWN)
        if not amount:
            return None, 'AmountTooLow'
        if param1:
            param1 = Decimal(param1)

        # Stop market validation
        if execution_type in Order.STOP_EXECUTION_TYPES:
            if not param1:
                return None, 'MissingStopPrice'

        # OCO pair validation
        if pair:
            if pair.pair_id is not None or pair.execution_type != Order.EXECUTION_TYPES.limit:
                return None, 'InvalidPair'
            if execution_type not in Order.STOP_EXECUTION_TYPES or amount != pair.amount:
                return None, 'InvalidPair'

        # Price Control
        if src_currency == Currencies.pmn and price > Decimal('0.085'):
            return None, 'MaxPaymonPriceIs0.085'

        # Price validation
        is_bad_price = False
        # Check price range based on orderbook
        check_orderbook_range = False
        if check_orderbook_range:
            orderbook_last_matching_price = cache.get('orderbook_{}_last_active_{}'.format(
                market_symbol, 'buy' if is_sell else 'sell'
            ))
            if orderbook_last_matching_price:
                if is_sell:
                    is_bad_price = price < orderbook_last_matching_price
                else:
                    is_bad_price = price > orderbook_last_matching_price
        # Extra checks for limit orders
        should_check_more = not is_bad_price and not settings.DISABLE_ORDER_PRICE_GUARD
        market_last_price = None
        if should_check_more and execution_type == Order.EXECUTION_TYPES.limit:
            # Check price with last trade in Nobitex market
            market_last_price, market_last_trade = cls.get_last_trade_data(market.id)
            if market_last_trade and market_last_price:
                duration = now() - market_last_trade
                allowed_change_percent = 10 + duration.total_seconds() // 60
                allowed_change = Decimal(0.01 * allowed_change_percent) * market_last_price
                if user.is_system_trader_bot:
                    allowed_change *= 150
                if user.id < 1000:
                    allowed_change *= 15
                if is_sell:
                    is_bad_price = price < market_last_price - allowed_change
                else:
                    is_bad_price = price > market_last_price + allowed_change
            # Also check price with global price
            if src_currency not in [Currencies.usdt, Currencies.gala, Currencies.sol]:
                mark_price = MarkPriceCalculator.get_mark_price(market.src_currency, market.dst_currency)
                if mark_price:
                    if is_sell:
                        is_bad_price = price < Decimal('0.8') * mark_price
                    else:
                        is_bad_price = price > Decimal('1.2') * mark_price
        if execution_type == Order.EXECUTION_TYPES.stop_market and price != param1:
            is_bad_price = price > param1 if is_sell else price < param1

        # Disallow order if the price is not in acceptable range
        if is_bad_price:
            log_event('BadPrice: {} {} {} U{}'.format(
                market_symbol,
                'Sell' if is_sell else 'Buy',
                f_m(price, c=dst_currency),
                user.id,
            ), level='info', module='market', category='notice', runner='api')
            return None, 'BadPrice'

        # OCO price condition check
        if pair:
            market_last_price = market_last_price or cache.get(f'market_{market.id}_last_price')
            if not market_last_price:
                market_last_price = (pair.price + param1) / 2
            if is_sell:
                price_condition = pair.price > market_last_price > param1 and pair.price > price
            else:
                price_condition = pair.price < market_last_price < param1 and pair.price < price
            if not price_condition:
                return None, 'PriceConditionFailed'

        # Create order object
        order_status = Order.STATUS.active
        if execution_type in Order.STOP_EXECUTION_TYPES:
            order_status = Order.STATUS.inactive

        order = Order(
            user=user,
            order_type=order_type,
            src_currency=src_currency,
            dst_currency=dst_currency,
            execution_type=execution_type,
            trade_type=trade_type,
            amount=amount,
            price=price,
            param1=param1,
            status=order_status,
            channel=channel,
            description=description,
            pair=pair,
            client_order_id=client_order_id,
        )

        # Check minimum order value - with a threshold to cover rounding issues
        if not settings.ALLOW_SMALL_ORDERS and not allow_small:
            if order.total_price < Decimal('0.99') * settings.NOBITEX_OPTIONS['minOrders'].get(dst_currency, 0):
                return False, 'SmallOrder'

        if order.is_spot:
            max_total_price = settings.NOBITEX_OPTIONS['maxOrders']['spot'][dst_currency]
        else:
            max_total_price = settings.NOBITEX_OPTIONS['maxOrders']['default'][dst_currency]

        # Check maximum order value - to cover transaction amount limit
        if not order.is_market and order.total_price >= max_total_price:
            return False, 'LargeOrder'

        # Validate order and save
        if not is_validated:
            ok, err = Wallet.validate_order(order, only_active_balance=True)
            if not ok:
                return None, err

        try:
            order.save()
        except IntegrityError as ex:
            if 'unique_user_client_order_id' in str(ex):
                return False, 'DuplicateClientOrderId'
            raise

        if pair:
            pair.pair_id = order.id
            pair.save(update_fields=('pair_id',))

        # Update caches and return
        uid = user.id
        cache.set(f'user_{uid}_recent_order', True, 100)
        transaction.on_commit(lambda: cache.set(f'user_{uid}_no_order', False, 60))
        if order.is_market:
            transaction.on_commit(lambda: cache.set(f'market_{market.id}_market_orders', 1))
        return order, None

    @classmethod
    def increase_order_matched_amount(cls, order, amount, price, fee=None):
        """Update order fields when it is matched
        Note: Order invalidation
        Changes are not saved yet
        """
        # TODO: is race-condition possible here?
        order.matched_amount += amount
        order.matched_total_price += (amount * price).quantize(MAX_PRECISION)
        if fee:
            order.fee += fee
        if order.is_matched:
            order.status = Order.STATUS.done
        elif order.is_trivial:
            order.status = Order.STATUS.canceled
        if order.pair:
            order.pair.pair = order
            order.pair.do_cancel()

    @classmethod
    def commit_trade(cls, trade):
        """Do the final steps of creating a trade. This method is
        called (only once) when a trade is determined to be committed
        to the DB.
        """
        from exchange.matcher.tradeprocessor import TradeProcessor

        # Updating related Order objects
        cls.increase_order_matched_amount(
            trade.sell_order,
            trade.matched_amount,
            trade.matched_price,
            fee=trade.get_sell_fee_amount(),
        )
        cls.increase_order_matched_amount(
            trade.buy_order,
            trade.matched_amount,
            trade.matched_price,
            fee=trade.get_buy_fee_amount(),
        )

        # Step 2: set tasks to run and update related data
        if not settings.ASYNC_TRADE_COMMIT:
            cls.publish_orders([trade])
            cls.commit_trade_async_step(trade)
            cls.create_trade_notif(trade)
            MarketManager.create_bulk_referral_fee([trade])
            cls.update_market_statistics([trade])
            TradeProcessor().process_trade(trade)

    @classmethod
    def commit_trade_async_step(cls, trade: OrderMatching):
        """Do the the final processing steps of a trade.
        Note: This method is not idempotent yet
        """
        # Non-critical steps
        try:
            trades_publisher(trade.symbol, cls.serialize_trade_public_data(trade, trade.symbol))

            private_trade_publisher(serialize_trade_for_user(trade, trade.seller_id), trade.seller.uid)
            private_trade_publisher(serialize_trade_for_user(trade, trade.buyer_id), trade.buyer.uid)

            # Send Web Engage Events
            cls.send_web_engage_events(trade)
        except Exception:
            report_exception()

    @staticmethod
    def publish_orders(trades: Iterable[OrderMatching]):

        order_publish_manager = OrderPublishManager()
        try:
            for trade in trades:
                order_publish_manager.add_order(trade.sell_order, trade, trade.seller.uid)
                order_publish_manager.add_order(trade.buy_order, trade, trade.buyer.uid)
            order_publish_manager.publish()
        except Exception:
            report_exception()


    @classmethod
    def create_trade_notif(cls, trade):
        """ Create notifications for both side of trade
        """
        msg = 'معامله انجام شد: {} {} {}'.format(
            '{}',
            f_m(trade.matched_amount, c=trade.src_currency, exact=True),
            _t(CURRENCY_CODENAMES.get(trade.src_currency)),
        )
        Notification.objects.create(user_id=trade.seller_id, message=msg.format('فروش'))
        Notification.objects.create(user_id=trade.buyer_id, message=msg.format('خرید'))

    @classmethod
    def send_web_engage_events(cls, trade):
        """Create celery tasks to send marketing events to Web Engage service."""
        OrderMatchedWebEngageEvent(
            order_type='Buy',
            user=trade.buyer,
            src_currency=trade.market.src_currency,
            dst_currency=trade.market.dst_currency,
            amount=trade.matched_price,
            channel=trade.buy_order.channel,
            trade_type=trade.buy_order.get_trade_type_display(),
            leverage=trade.buy_order.leverage,
        ).send()
        OrderMatchedWebEngageEvent(
            order_type='Sell',
            user=trade.seller,
            src_currency=trade.market.src_currency,
            dst_currency=trade.market.dst_currency,
            amount=trade.matched_price,
            channel=trade.sell_order.channel,
            trade_type=trade.sell_order.get_trade_type_display(),
            leverage=trade.sell_order.leverage,
        ).send()

    @classmethod
    def create_referral(cls, referrer: UserReferral, restrictions: Dict, trade: OrderMatching, *, is_sell: bool):
        dst_to_rial = trade.rial_value / trade.matched_total_price
        fee = trade.get_sell_fee_amount() if is_sell else trade.get_buy_fee_amount() * trade.matched_price
        total_value = fee * dst_to_rial * Decimal('0.01')

        referrals = [
            cls.create_parent_referral_fee(referrer, restrictions, trade.pk, total_value),
            cls.create_child_referral_fee(referrer, restrictions, trade.pk, total_value),
        ]
        return list(filter(lambda r: r is not None, referrals))

    @staticmethod
    def create_parent_referral_fee(
        referrer: UserReferral, restrictions: Dict, matching_id: int, total_value: Decimal
    ) -> Optional[ReferralFee]:

        if not referrer.referral_share:
            return None

        if (
            'parent_share_eligible_months' in restrictions
            and (ir_now() - timedelta(days=restrictions['parent_share_eligible_months'] * 30)) > referrer.created_at
        ):
            return None

        return ReferralFee(
            user=referrer.parent,
            referred_user_id=referrer.child_id,
            referral_program_id=referrer.referral_program_id,
            matching_id=matching_id,
            amount=round(total_value * Decimal(referrer.referral_share)),
        )

    @staticmethod
    def create_child_referral_fee(
        referrer: UserReferral, restrictions: Dict, matching_id: int, total_value: Decimal
    ) -> Optional[ReferralFee]:

        if not referrer.child_referral_share:
            return None

        if (
            'child_share_eligible_months' in restrictions
            and (ir_now() - relativedelta(months=restrictions['child_share_eligible_months'])) > referrer.created_at
        ):
            return None

        return ReferralFee(
            user=referrer.child,
            referred_user_id=referrer.child_id,
            referral_program_id=referrer.referral_program_id,
            matching_id=matching_id,
            amount=round(total_value * Decimal(referrer.child_referral_share)),
        )

    @staticmethod
    def get_user_referrals(trades):
        user_ids = []
        for trade in trades:
            user_ids.append(trade.seller_id)
            user_ids.append(trade.buyer_id)
        return UserReferral.objects.filter(child__in=user_ids).in_bulk(field_name='child_id')

    @classmethod
    def create_bulk_referral_fee(cls, trades):
        restrictions = Settings.get_cached_json('referral_fee_restrictions', {})
        user_referrals = cls.get_user_referrals(trades)

        referrals = []
        for trade in trades:
            seller_referral = user_referrals.get(trade.seller_id)
            if seller_referral:
                referrals += cls.create_referral(seller_referral, restrictions, trade, is_sell=True)

            buyer_referral = user_referrals.get(trade.buyer_id)
            if buyer_referral:
                referrals += cls.create_referral(buyer_referral, restrictions, trade, is_sell=False)

        ReferralFee.objects.bulk_create(referrals, batch_size=1000)

    @classmethod
    def update_recent_trades_cache(cls, symbol):
        with measure_time_cm(metric='update_recent_trades_cache', labels=[symbol]):
            raw_recent_trades = cache.get(f'trades_{symbol}', default='[]')
            try:
                if not isinstance(prev_recent_trades := json.loads(raw_recent_trades), list):
                    prev_recent_trades = []
            except (json.JSONDecodeError, TypeError):
                prev_recent_trades = []

            if (
                prev_recent_trades
                and isinstance(last_trade_time := prev_recent_trades[-1].get('time'), int)
            ):
                first_trade_created_at = parse_utc_timestamp_ms(last_trade_time)
            else:
                first_trade_created_at = now() - datetime.timedelta(days=2 if settings.IS_PROD else 7)

            trades = (
                OrderMatching.objects.filter(
                    market=Market.by_symbol(symbol),
                    created_at__gte=first_trade_created_at,
                    matched_amount__gt=0,  # Excluding reversed trades
                )
                .select_related(
                    'sell_order',
                    'buy_order',
                )
                .order_by('-created_at')[:20]
            )

            serialized_latest_20_trades = [cls.serialize_trade_public_data(trade, symbol) for trade in trades]

            recent_trades = json.dumps(serialized_latest_20_trades, separators=(',', ':'))
            cache.set(f'trades_{symbol}', recent_trades)
            return recent_trades

    @staticmethod
    def serialize_trade_public_data(trade: OrderMatching, symbol: str) -> dict:
        return {
            'time': serialize_timestamp(trade.created_at),
            'price': serialize_decimal(trade.matched_price, {'symbol': symbol, 'context': 'price'}),
            'volume': serialize_decimal(
                trade.matched_amount, {'symbol': symbol, 'context': 'amount', 'rounding': 'up'}
            ),
            'type': 'sell' if trade.is_market_sell else 'buy',
        }

    @classmethod
    def get_bulk_latest_user_stats(cls, date_from, missed_days):
        """Update UserTradeStatus for users who have trades between date_from and last night"""
        last_midnight = ir_now().replace(hour=0, minute=0, second=0, microsecond=0)
        month_ago = last_midnight - datetime.timedelta(days=30)

        if missed_days <= 7:
            month_data = cls.get_incremental_trades_aggregates(date_from, last_midnight, month_ago, missed_days)
        else:
            month_data = cls.get_cumulative_trades_aggregates(month_ago, last_midnight)
            UserTradeStatus.objects.filter(updated_at__gte=month_ago - datetime.timedelta(days=missed_days)).exclude(
                user_id__in=month_data
            ).exclude(month_trades_count=0).update(
                month_trades_total=Decimal('0'),
                month_trades_count=0,
            )
        # Update trade status
        cache_ttl = 26 * 3600
        existing_user_trade_status = UserTradeStatus.objects.filter(
            user_id__in=month_data,
        )
        existing_trades_user_ids = set(existing_user_trade_status.values_list('user_id', flat=True))
        existing_user_trade_status = existing_user_trade_status.exclude(updated_at__gte=last_midnight)
        update_time = ir_now()
        for batch_user_trade_status in batcher(existing_user_trade_status, batch_size=500, idempotent=True):
            for trade_status in batch_user_trade_status:
                if missed_days <= 7:
                    trade_status.month_trades_total += month_data[trade_status.user_id]['month_trades_total']
                    trade_status.month_trades_count += month_data[trade_status.user_id]['month_trades_count']
                else:
                    trade_status.month_trades_total = month_data[trade_status.user_id]['month_trades_total']
                    trade_status.month_trades_count = month_data[trade_status.user_id]['month_trades_count']
                trade_status.updated_at = update_time
                cache.set(f'user_{trade_status.user_id}_vipLevel', trade_status.vip_level, cache_ttl)
                cache.set(f'user_{trade_status.user_id}_trade_status', trade_status, cache_ttl)
            UserTradeStatus.objects.bulk_create(
                batch_user_trade_status,
                update_fields=('month_trades_total', 'month_trades_count', 'updated_at'),
                update_conflicts=True,
                unique_fields=('id',),
                batch_size=50,
            )

        new_trades_user_ids = set(month_data.keys()) - existing_trades_user_ids
        update_time = ir_now()
        new_user_trade_status = [
            UserTradeStatus(user_id=user_id, **month_data[user_id], updated_at=update_time)
            for user_id in new_trades_user_ids
        ]
        user_trade_status = UserTradeStatus.objects.bulk_create(new_user_trade_status, batch_size=500)
        for trade_status in user_trade_status:
            cache.set(f'user_{trade_status.user_id}_vipLevel', trade_status.vip_level, cache_ttl)
            cache.set(f'user_{trade_status.user_id}_trade_status', trade_status, cache_ttl)

    @classmethod
    def get_latest_user_stats(cls, user, force_update=False):
        """ Return UserTradeStatus for the given user """

        # We only use user id from the user object
        if isinstance(user, int):
            user_id = user
        else:
            user_id = user.id

        # Return from cache if available
        cache_key = 'user_{}_trade_status'.format(user_id)
        default_cache_ttl = 26 * 3600
        if not force_update:
            trade_status = cache.get(cache_key)
            if not trade_status:
                trade_status = UserTradeStatus.objects.get_or_create(user_id=user_id)[0]
                cache.set(cache_key, trade_status, default_cache_ttl)
                cache.set(f'user_{user_id}_vipLevel', trade_status.vip_level, default_cache_ttl)
            return trade_status

        # Calculate month trades
        last_midnight = ir_now().replace(hour=0, minute=0, second=0, microsecond=0)
        month_ago = last_midnight - datetime.timedelta(days=30)
        month_data = OrderMatching.get_trades(user=user_id, date_from=month_ago, date_to=last_midnight,).aggregate(
            total=Sum('rial_value'),
            count=Count('*'),
            first=Min('created_at'),
        )

        # Calculate trades in trader plan to exclude from total
        month_trades_total_trader = Decimal('0')
        plans = UserPlan.objects.filter(
            Q(date_to__isnull=True) | Q(date_to__gt=month_ago),
            user_id=user_id,
            type=UserPlan.TYPE.trader,
        )
        for plan in plans:
            if not plan.date_to:
                plan.date_to = ir_now()
            trades = OrderMatching.get_trades(
                user=user_id,
            ).filter(created_at__range=[max(plan.date_from, month_ago), plan.date_to])
            month_trades_total_trader += trades.aggregate(
                total=Sum('rial_value')
            )['total'] or Decimal(0)

        # Update trade status
        trade_status = UserTradeStatus.objects.get_or_create(user_id=user_id)[0]
        trade_status.month_trades_count = month_data['count'] or 0
        trade_status.month_trades_total = month_data['total'] or Decimal('0')
        trade_status.month_trades_total_trader = month_trades_total_trader
        trade_status.updated_at = now()
        trade_status.save()

        # Cache user vipLevel
        cache.set(f'user_{user_id}_vipLevel', trade_status.vip_level, default_cache_ttl)

        # Cache trade status
        exp_time = datetime.timedelta(days=30)
        first_trade = month_data['first']
        if first_trade:
            exp_time -= now() - first_trade
        cache_ttl = exp_time.total_seconds()
        cache.set(cache_key, trade_status, min(cache_ttl, 604800))
        return trade_status

    @classmethod
    def update_market_statistics(cls, trades: Union[QuerySet[OrderMatching], List[OrderMatching]]):
        if len(trades) == 0:
            return

        last_trade = trades[len(trades) - 1]
        # Update last price caches
        cache.set_many(
            {
                f'market_{last_trade.market_id}_last_price': last_trade.matched_price,
                f'market_{last_trade.market_id}_last_trade': last_trade.created_at,
            }
        )
        # Market daily count
        metric_name = f'market_{last_trade.market_id}_daily_count'
        metric_incr(metric_name, len(trades))

    @classmethod
    def create_sell_whole_balance_order(cls, wallet, dst_currency, channel=None):
        """Create a sell order to sell all of a wallets balance, even if it is
            below minimum order value.
        """
        if money_is_zero(wallet.active_balance):
            return None, 'InsufficientBalance'
        return cls.create_order(
            user=wallet.user,
            order_type=Order.ORDER_TYPES.sell,
            execution_type=Order.EXECUTION_TYPES.market,
            src_currency=wallet.currency,
            dst_currency=dst_currency,
            amount=wallet.active_balance,
            is_validated=True,
            allow_small=True,
            channel=channel,
        )

    @classmethod
    def get_incremental_trades_aggregates(
        cls, date_from: datetime.datetime, date_to: datetime.datetime, month_date: datetime.datetime, days_count: int
    ) -> Dict[int, UserTradesData]:
        """
        calculate trades amounts and counts for 2 timeframes:
        1) [date_from, date_to]
        2) [month_date - days_count, month_date]
        to have data of last month trades, trades of first timeframe will be added to data
        and trades of second timeframe will be subtracted.
        """
        month_data = defaultdict(lambda: {'month_trades_total': Decimal('0'), 'month_trades_count': 0})

        for user_type in ['seller', 'buyer']:
            for dates in [[date_from, date_to], [month_date - datetime.timedelta(days=days_count), month_date]]:
                trades_data = (
                    OrderMatching.get_trades(
                        date_from=dates[0],
                        date_to=dates[1],
                    )
                    .values(user_type + '_id')
                    .annotate(
                        total=Sum('rial_value'),
                        count=Count('*'),
                    )
                )

                trades_dict = {trade[user_type + '_id']: trade for trade in trades_data}
                for user_id, user_value in trades_dict.items():
                    if dates[0] == date_from:
                        month_data[user_id]['month_trades_total'] += user_value['total']
                        month_data[user_id]['month_trades_count'] += user_value['count']
                    else:
                        month_data[user_id]['month_trades_total'] -= user_value['total']
                        month_data[user_id]['month_trades_count'] -= user_value['count']

        return month_data

    @classmethod
    def get_cumulative_trades_aggregates(
        cls, date_from: datetime.datetime, date_to: datetime.datetime
    ) -> Dict[int, UserTradesData]:
        """Calculate total trades amounts and counts for users between date_from and date_to"""
        month_data = defaultdict(lambda: {'month_trades_total': Decimal('0'), 'month_trades_count': 0})
        month_trades = OrderMatching.objects.filter(created_at__range=[date_from, date_to])

        for user_type in ['seller', 'buyer']:
            trades = month_trades.values(user_type + '_id').annotate(
                total=Sum('rial_value'),
                count=Count('*'),
            )
            trades_dict = {trade[user_type + '_id']: trade for trade in trades}
            for user_id, user_value in trades_dict.items():
                month_data[user_id]['month_trades_total'] += user_value['total']
                month_data[user_id]['month_trades_count'] += user_value['count']

        return month_data
