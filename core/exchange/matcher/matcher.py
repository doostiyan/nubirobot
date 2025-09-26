""" Matching Engine Main Logic
"""
import contextlib
import datetime
import itertools
from decimal import ROUND_DOWN, Decimal
from functools import partial
from typing import ClassVar, Dict, Iterable, List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q, QuerySet, Subquery
from django.utils import timezone

from exchange.accounts.models import Notification, User
from exchange.accounts.userstats import UserStatsManager
from exchange.base.constants import MAX_PRECISION, PRICE_GUARD_RANGE, ZERO
from exchange.base.decorators import measure_time_cm, ram_cache
from exchange.base.locker import Locker
from exchange.base.logging import log_event, report_event, report_exception
from exchange.base.models import (
    AMOUNT_PRECISIONS,
    MATCHER_GET_ORDER_MONITORING_SYMBOLS,
    MATCHER_MATCH_TIME_MONITORING_SYMBOLS,
    RIAL,
    TETHER,
)
from exchange.base.models import Settings as NobitexSettings
from exchange.base.money import money_is_zero
from exchange.base.publisher import OrderPublishManager
from exchange.base.serializers import serialize_timestamp
from exchange.margin.models import MarginOrderChange
from exchange.margin.tasks import task_bulk_update_position_on_order_change, task_liquidate_positions
from exchange.market.constants import MARKET_ORDER_MAX_PRICE_DIFF
from exchange.market.functions import post_process_updated_margin_orders
from exchange.market.marketmanager import MarketManager
from exchange.market.markprice import MarkPriceCalculator
from exchange.market.models import Market, Order, OrderMatching
from exchange.market.tasks import (
    task_batch_commit_trade_async_step,
    task_notify_stop_order_activation,
    task_update_recent_trades_cache,
)
from exchange.market.ws_serializers import serialize_order_for_user
from exchange.matcher.constants import MIN_PRICE_PRECISION, STOPLOSS_ACTIVATION_MARK_PRICE_GUARD_RATE
from exchange.matcher.exceptions import MatchingError
from exchange.matcher.timer import MarketTimer
from exchange.usermanagement.block import BalanceBlockManager
from exchange.wallet.models import Wallet


class Matcher:
    # Caches
    SHARED_TETHER_DATA: ClassVar = {}

    USERS_WITH_MANUAL_FEE: ClassVar[Dict[int, User]] = {}
    MAX_TRADE_PER_ROUND: int = 5 * 40  # i.e. 5 seconds with 40 TPS
    ORDERBOOK_CRITERIA_AGE_VALIDITY_IN_SECONDS = 300 if settings.IS_TESTNET else 2
    ORDERBOOK_RUNTIME_LIMITATION_MARKETS_SETTINGS_KEY = 'matcher_order_book_runtime_limitation_markets'
    EXPANDABLE_MARKETS_SETTINGS_KEY = 'matcher_expandable_markets'
    ASYNC_STOP_PROCESS_MARKETS_SETTINGS_KEY = 'matcher_async_stop_process_markets'

    MARKET_LAST_PROCESSED_TIME: ClassVar[Dict[int, datetime.datetime]] = {}
    MARKET_LAST_BEST_PRICES: ClassVar[Dict[int, Tuple[Decimal, Decimal]]] = {}
    MARKET_PRICE_RANGE: ClassVar[Dict[int, Tuple[Decimal, Decimal]]] = {}

    EXPANSION_THRESHOLD: int = 200
    EXPANSION_STEP: int = 20

    def __init__(
        self,
        market,
        thread_name='Non',
    ):
        self.market = market
        self.src_currency = market.src_currency
        self.dst_currency = market.dst_currency
        self.market_is_usdt_pair = self.dst_currency == TETHER
        self.market_is_buy_in_promotion = MarketManager.is_market_in_promotion(
            self.src_currency,
            self.dst_currency,
            is_buy=True,
        )
        self.market_is_sell_in_promotion = MarketManager.is_market_in_promotion(
            self.src_currency,
            self.dst_currency,
            is_buy=False,
        )
        self.VALIDATED_ORDERS = set()
        self.LAST_PRICE_RANGE = []

        self.report = {'matches': 0, 'failures': 0, 'skipped': 0}
        self.pending_orders_for_update = set()
        self.pending_canceled_orders = set()
        self.pending_cache_transactions = {}
        self.timer = MarketTimer()
        self.thread_name = thread_name

        self.tether_market_id = self.SHARED_TETHER_DATA.get('market_id')
        self.tether_price = self.SHARED_TETHER_DATA.get('price')

        # these variables are initialized from redis cache
        self.orderbook_update_datetime = None
        self.price_range_low: Optional[Decimal] = None
        self.price_range_high: Optional[Decimal] = None

        self.orderbook_best_buy_price = None
        self.orderbook_best_sell_price = None
        self._get_cached_data()


        self.last_expanded_buy_order: Optional[Order] = None
        self.last_expanded_sell_order: Optional[Order] = None
        self.expansion_sells_len = 0
        self.expansion_buys_len = 0
        self.rounds_of_buys_expansion = 0
        self.rounds_of_sells_expansion = 0
        self.is_orderbook_outdated: Optional[bool] = None

    def _get_cached_data(self):
        orderbook_cache_keys = [
            f'orderbook_{self.market.symbol}_{kind}_active_{side}'
            for kind, side in itertools.product(('last', 'best'), ('buy', 'sell'))
        ] + [f'orderbook_{self.market.symbol}_update_time']
        orderbook_cache_data = cache.get_many(orderbook_cache_keys)

        self.price_range_low = Decimal(orderbook_cache_data.get(orderbook_cache_keys[0]) or '0')
        self.price_range_high = Decimal(orderbook_cache_data.get(orderbook_cache_keys[1]) or '0')

        self.orderbook_best_buy_price = Decimal(orderbook_cache_data.get(orderbook_cache_keys[2]) or '0')
        self.orderbook_best_sell_price = Decimal(orderbook_cache_data.get(orderbook_cache_keys[3]) or '0')

        orderbook_update_timestamp = int(
            orderbook_cache_data.get(
                f'orderbook_{self.market.symbol}_update_time',
                serialize_timestamp(timezone.now()),
            ),
        )
        self.orderbook_update_datetime = timezone.make_aware(
            datetime.datetime.fromtimestamp(orderbook_update_timestamp / 1000),
        )

    def _write_log(self, message, end=''):
        message = self.thread_name + ':' + f'Market[{self.market.symbol}] ' + message
        print(message + '\n', end=end, flush=True)

    @classmethod
    def initialize_globals(cls):
        """Set initial value for class global variables from cache."""
        tether_market = Market.get_for(TETHER, RIAL)
        if not tether_market:
            print('Warning: Cannot get USDTIRT market.', flush=True)
            return

        cls.SHARED_TETHER_DATA['market_id'] = tether_market.id
        cls.SHARED_TETHER_DATA['price'] = cache.get(f'market_{tether_market.id}_last_price')

    @classmethod
    def reinitialize_caches(cls) -> None:
        """Update cache stores used in matcher instances. It should always
        run once before any run of matcher, and may be called anytime afterward
        to update the caches."""
        cls.get_user_vip_level.clear()
        cls.USERS_WITH_MANUAL_FEE.clear()
        manual_fee_users = User.objects.exclude(
            base_fee__isnull=True,
            base_maker_fee__isnull=True,
            base_fee_usdt__isnull=True,
            base_maker_fee_usdt__isnull=True,
        ).only('id', 'base_fee', 'base_fee_usdt', 'base_maker_fee', 'base_maker_fee_usdt')
        for user in manual_fee_users:
            cls.USERS_WITH_MANUAL_FEE[user.id] = user

    @classmethod
    def debug(cls, *args, **kwargs):
        """Log debug info."""
        if settings.IS_TEST_RUNNER:
            print(*args, **kwargs, flush=True)

    @classmethod
    def get_pending_markets(cls, *, cache_based: bool = False) -> Iterable[Market]:
        if cache_based:
            return cls._get_cache_based_pending_markets()
        return cls._get_db_based_pending_markets()

    @classmethod
    def _get_db_based_pending_markets(cls) -> QuerySet[Market]:
        """Find market pairs expecting trades using orders table"""
        active_orders = Order.objects.filter(
            src_currency=OuterRef('src_currency'),
            dst_currency=OuterRef('dst_currency'),
            status=Order.STATUS.active,
        )
        limit_order_prices = active_orders.exclude(execution_type__in=Order.MARKET_EXECUTION_TYPES).values('price')
        return (
            Market.objects.filter(is_active=True)
            .annotate(
                best_buy=Subquery(limit_order_prices.filter(order_type=Order.ORDER_TYPES.buy).order_by('-price')[:1]),
                best_sell=Subquery(limit_order_prices.filter(order_type=Order.ORDER_TYPES.sell).order_by('price')[:1]),
                has_market=Exists(active_orders.filter(execution_type__in=Order.MARKET_EXECUTION_TYPES)),
            )
            .exclude(has_market=False, best_buy__lt=F('best_sell'))
        )

    def _use_orderbook_runtime_limit_logic(self):
        return self.market.symbol in self._get_symbols_that_use_runtime_limit_logic()

    def _do_expansion(self):
        return self.market.symbol in self._get_symbols_that_use_expansion()

    @classmethod
    @ram_cache()
    def _get_symbols_that_use_runtime_limit_logic(cls):
        return NobitexSettings.get_cached_json(cls.ORDERBOOK_RUNTIME_LIMITATION_MARKETS_SETTINGS_KEY, default='[]')

    @classmethod
    @ram_cache()
    def _get_symbols_that_use_expansion(cls):
        return NobitexSettings.get_cached_json(cls.EXPANDABLE_MARKETS_SETTINGS_KEY, default='[]')

    @classmethod
    @ram_cache()
    def get_symbols_that_use_async_stop_process(cls):
        return NobitexSettings.get_cached_json(cls.ASYNC_STOP_PROCESS_MARKETS_SETTINGS_KEY, default='[]')

    @classmethod
    def _get_cache_based_pending_markets(cls) -> List[Market]:
        """Find market pairs expecting trades using orderbook caches"""
        markets = Market.objects.filter(is_active=True)

        orderbook_cache_keys = {market.id: f'orderbook_{market.symbol}_skips' for market in markets}
        api_cache_keys = {market.id: f'market_{market.id}_market_orders' for market in markets}

        cache_values = cache.get_many(tuple(orderbook_cache_keys.values()) + tuple(api_cache_keys.values()))
        cache.set_many({key: 0 for key, value in cache_values.items() if value})

        return [
            market
            for market in markets
            if cache_values.get(orderbook_cache_keys[market.id]) or cache_values.get(api_cache_keys[market.id])
        ]

    def _cancel_order(self, order: Order):
        order.status = Order.STATUS.canceled
        self.pending_canceled_orders.add(order)

    @classmethod
    @ram_cache(timeout=3600)
    def get_user_vip_level(cls, user_id: int) -> int:
        """Get user vip level by id, trying to use cache to minimize queries."""
        return UserStatsManager.get_user_vip_level(user_id)

    def validate_order(self, order, *, use_cache=True):
        """Check order to have enough balance, also canceling it if not."""
        if use_cache and order.id in self.VALIDATED_ORDERS:
            return True
        self.timer.start_timer()
        is_valid, error = Wallet.validate_order(order)
        self.timer.end_timer('GetWallets')
        if is_valid:
            self.VALIDATED_ORDERS.add(order.id)
            return True
        self._cancel_order(order)
        self._write_log(f'{error}#{order.id}', end=' ')
        if order.id in self.VALIDATED_ORDERS:
            self.VALIDATED_ORDERS.remove(order.id)
        return False

    @staticmethod
    def update_blocked_balance(wallet):
        """Update wallet balance_blocked in memory"""
        if wallet.user_id in settings.TRUSTED_USER_IDS:
            return
        wallet.balance_blocked = BalanceBlockManager.get_blocked_balance(wallet)

    def check_for_forbidden_matching(self, sell, buy):
        """Check for special bad cases in matchings. These cases are usually problematic,
        so we cancel both orders.
        """
        # These checks are only active in production
        if not settings.PREVENT_INTERNAL_TRADE:
            return True
        # Do not match automatic orders of system trader bots with each other
        if sell.user_id in settings.TRADER_BOT_IDS and buy.user_id in settings.TRADER_BOT_IDS:
            self._cancel_order(sell)
            self._cancel_order(buy)
            self._write_log('\t!Skip !SelfMatch', end=' ')
            return False
        return True

    def do_matching_round(self):
        """Matching Round - A single pass on the market orders
        to process all matching orders. Main required locks
        for concurrency control are managed here.
        """
        self.timer.start_timer()
        with transaction.atomic():
            Locker.require_lock('matcher_market_lock', self.market.pk)
            self.timer.end_timer('MarketLock')
            self._write_log(f'{self.market.symbol:<10}', end='')
            self.process_market_orders()
        self.timer.end_timer('COMMIT')  # Main DB transaction COMMIT duration
        # Set Price Range For Special Order Types Processing
        if self.market.symbol in self.get_symbols_that_use_async_stop_process():
            self.MARKET_PRICE_RANGE[self.market.id] = self.LAST_PRICE_RANGE
        else:
            post_processing_matcher_round(self.market, self.LAST_PRICE_RANGE, self.timer)

    def process_market_orders(self, effective_date=None):
        """Main exchange logic for matching buy and sell orders in a market"""
        # Getting orders
        effective_date = effective_date or timezone.now()
        sells, buys = self.get_market_orders()

        # Log for beta markets.
        with measure_time_cm(
            metric='matcher_match_time',
            labels=[self.market.symbol],
        ) if self.market.symbol in MATCHER_MATCH_TIME_MONITORING_SYMBOLS else contextlib.nullcontext():
            self.match_all_orders_v3(sells, buys, effective_date)

        self.post_process_orders(buys, sells)
        if self.report['matches']:
            transaction.on_commit(lambda: task_update_recent_trades_cache.delay(self.market.symbol))

        if settings.ASYNC_TRADE_COMMIT:
            transaction.on_commit(lambda: task_batch_commit_trade_async_step.delay(effective_date, self.market.id))

    def match_all_orders_v3(self, sells, buys, effective_date):
        """New matching logic, based on processing new top orders one by one."""
        # Detect new important orders since last matching round.
        #
        # Important orders are new orders with prices (strictly) better than each
        #  previous top of orderbook in each side. For example any market order is
        #  important.
        #
        # L1: At the end of each matching round, all possible matchings are executed.
        # L2: At the end of each matching round, there are no possible
        #  matchings in orders with created_at<last_time.
        # L3: Any new matching must have one important order.
        #
        # Market orders do not need special cases because orders are sorted so that market
        #  orders are on the top of orderbooks.
        # At the start of matching, all orders are considered important. This may be inefficient
        #  but because it is possible for many orders to be batched on a single matching round,
        #  for example in slowdowns or restarts, we process all such orders (limited to ~200 by
        #  orderbook heuristic) one by one.
        last_time = self.MARKET_LAST_PROCESSED_TIME.get(self.market.id, settings.NOBITEX_EPOCH)
        last_best_sell, last_best_buy = self.MARKET_LAST_BEST_PRICES.get(self.market.id, (ZERO, Decimal('Inf')))

        new_orders = []
        for orders in [sells, buys]:
            for order in orders:
                if (
                    order.is_market
                    or order.created_at >= last_time
                    or (order.price < last_best_sell if order.is_sell else order.price > last_best_buy)
                ):
                    new_orders.append(order)

        # Run matching loop, adding one important new order at each round.
        #  So in each run only one effective new order is added and the resulting
        #  matchings are serializable.
        # We assume that the main contributor to matching time is DB access (and cache
        #  access a distant second), so the processing and loops in python code are
        #  negligible and we run them freely.
        for order in sorted(new_orders, key=lambda o: (o.created_at, o.id)):
            self.match_all_orders_before_order(sells, buys, effective_date, last_order=order)
            if order.is_market and order.is_active:
                self._cancel_order(order)
                self._write_log(f'    CanceledMarketOrder:#{order.pk}  {order.price:.8f} ')
            if not order.is_market:
                last_time = order.created_at
            if self.report['matches'] >= self.MAX_TRADE_PER_ROUND:
                self._write_log('    Reserve further matching for next round')
                break
        else:
            # Run once more to be sure all matching are done,
            #  but this should not result in any new matchings because of L3.
            matches = self.report['matches']
            self.match_all_orders_before_order(sells, buys, effective_date, last_order=None)
            if self.report['matches'] > matches:
                symbol = self.market.symbol
                log_event(
                    f'MissedMatching: {symbol} Last={last_time}',
                    level='warning',
                    category='notice',
                    module='market',
                    runner='matcher',
                )
                Notification.notify_admins(f'{symbol}:{last_time}', title='‼️MissedMatching', channel='matcher')
                missed_matchings_cnt = self.report['matches'] - matches
                self.timer.update_missed_matchings_metric(missed_matchings_cnt)

        self.timer.start_timer()
        # Save changed fields in trades and orders
        self.save_bulk_pending_orders()
        self.timer.end_timer('CommitTrade')

        # Set transactions data
        if settings.ASYNC_TRADE_COMMIT:
            cache.set_many(data=self.pending_cache_transactions, timeout=1800)

        # Done. Update last_time to the latest important order that was checked.
        #  ALso save best active price on both sides of orderbook.
        #  It is not set to the last existing order, because only the first order
        #  in each orderbook side matter, and only important orders can take such
        #  place.
        self.MARKET_LAST_PROCESSED_TIME[self.market.id] = last_time
        self.MARKET_LAST_BEST_PRICES[self.market.id] = (
            self._get_best_active_price(sells, last_time) or ZERO,
            self._get_best_active_price(buys, last_time) or Decimal('Inf'),
        )

        self.debug('REPORT', self.report)

    @staticmethod
    def _get_best_active_price(side_orders, last_time) -> Optional[Decimal]:
        for order in side_orders:
            if order.is_active and not order.is_market and order.created_at <= last_time:
                return order.price

    def save_bulk_pending_orders(self):
        if self.pending_orders_for_update:
            Order.objects.bulk_update(
                list(self.pending_orders_for_update),
                ['status', 'fee', 'matched_amount', 'matched_total_price'],
                batch_size=10,
            )
            post_process_updated_margin_orders(self.pending_orders_for_update)

    def match_all_orders_before_order(self, sells, buys, effective_date, last_order: Optional[Order] = None):
        """Run matching loop, considering only orders with created_at=<last_time."""
        if last_order:
            if last_order.is_sell:
                sells = [last_order]
            else:
                buys = [last_order]
        for sell in sells:
            if last_order and sell.created_at > last_order.created_at:
                continue
            for buy in buys:
                if last_order and buy.created_at > last_order.created_at:
                    continue

                # Skip Matched/Canceled Orders
                # Also if the order with created_at=last_time is done or canceled, this function
                #  has processed all possible orders and should return.
                if sell.is_matched or not sell.is_active:
                    if sell == last_order:
                        return
                    break
                if buy.is_matched or not buy.is_active:
                    if buy == last_order:
                        return
                    continue

                # Handle Market Orders
                is_market_trade = buy.is_market or sell.is_market
                if buy.is_market and sell.is_market:
                    # two market orders cannot be matched together, so skip this
                    #  pair and match buy market orders after all sell market
                    #  orders are matched
                    continue

                # Check if buy-sell orders can be matched together
                if buy.price < sell.price and not is_market_trade:
                    return

                # Final order validation before match
                if not self.check_for_forbidden_matching(sell, buy):
                    self.report['failures'] += 1
                    return

                if not self.validate_order(buy):
                    continue
                if not self.validate_order(sell):
                    break

                # Orders matched! Creating and committing t
                # he exchange transactions
                matching = self.match_two_orders(sell, buy, effective_date)
                self.report['matches' if matching else 'skipped'] += 1

        if not self._do_expansion():
            self.debug('\treport', self.report)

            return

        # if the price range in the current orders (sells or buys) is over
        # the last_order price then there is no need to go for expansion.
        # for example, last_order sells for $90 but our buys contains $80 which
        # means expansion cannot help us.
        if not last_order or last_order.is_market:
            self.debug('\treport', self.report)

            return

        if last_order.is_buy and len(sells) > 0 and sells[-1].price > last_order.price:
            self.debug('\treport', self.report)

            return

        if last_order.is_sell and len(buys) > 0 and last_order.price > buys[-1].price:
            self.debug('\treport', self.report)

            return

        # expanding the price to fetch more orders to fill out the partially matched order. (core#3639)
        # exending at this step is reflected over the actual buys or sells list because we are changing
        # the actual list with extend.
        if (
            last_order
            and last_order.is_active
            and not last_order.is_trivial
            and len(
                expansion := self.get_market_orders_with_expansion(
                    is_buy=last_order.is_buy,
                ),
            )
            > 0
        ):
            if last_order.is_buy:
                sells.extend(expansion)
            else:
                buys.extend(expansion)

            self.match_all_orders_before_order(sells, buys, effective_date, last_order=last_order)

        self.debug('\treport', self.report)

    def post_process_orders(self, buys, sells):
        """Do the final steps, after all possible matchings are done."""
        self.timer.start_timer()

        # Post-process 1: find expired and unfilled Margin/ABC system orders
        system_margin_expiry_threshold = timezone.now() - settings.MARGIN_SYSTEM_ORDERS_MAX_AGE
        margin_system_orders = set()
        for orders_list in [buys, sells]:
            for order in orders_list:
                if (
                    order.channel in {Order.CHANNEL.system_margin, Order.CHANNEL.system_abc_liquidate}
                    and order.created_at < system_margin_expiry_threshold
                ):
                    self._write_log(
                        'UnfilledMarginSystemOrder'
                        if order.channel == Order.CHANNEL.system_margin
                        else 'UnfilledABCLiquidateSystemOrder',
                        end=' ',
                    )
                    margin_system_orders.add(order)

        # Post-process 3: remove bulk updated orders
        not_updated_orders = self.pending_canceled_orders - self.pending_orders_for_update
        not_updated_orders = not_updated_orders | margin_system_orders
        order_ids = [order.id for order in not_updated_orders]
        order_ids.extend([order.pair_id for order in not_updated_orders if order.pair_id])

        # Post-process 4: update status
        canceled_orders = (
            Order.objects.filter(id__in=order_ids).order_by('created_at').update(status=Order.STATUS.canceled)
        )
        # Post-process 5: call signals
        post_process_updated_margin_orders(not_updated_orders)
        self.timer.end_timer('CancelOrders')
        all_orders = len(sells) + len(buys)
        self.timer.update_orders_metric(all_orders, canceled_orders)

    def match_two_orders(self, sell, buy, effective_date):
        self.timer.start_timer()

        # Update blocked balances for wallets
        self.update_blocked_balance(sell.src_wallet)
        self.update_blocked_balance(buy.dst_wallet)
        self.timer.end_timer('BlockedBalances')

        # Check Assumption: Both sides are not market orders
        if buy.is_market and sell.is_market:
            raise ValueError('DualMarketOrderMatching')

        # Determine maker
        if sell.is_market:
            is_seller_maker = False
        elif buy.is_market:
            is_seller_maker = True
        else:
            # Maker is determined by the first order that entered orderbook
            is_seller_maker = sell.created_at <= buy.created_at

        # Determine match price
        matched_price = sell.price if is_seller_maker else buy.price

        # Market precision
        market_symbol = self.market.symbol
        amount_precision = AMOUNT_PRECISIONS[market_symbol]

        # Determining match amount
        matched_amount = min(buy.unmatched_amount, sell.unmatched_amount)
        trade_total = matched_amount * matched_price
        buyer_wallet = buy.dst_wallet
        buyer_available_balance = buyer_wallet.balance - buyer_wallet.balance_blocked
        if trade_total > buyer_available_balance:
            matched_amount = buyer_available_balance / matched_price
            matched_amount = matched_amount.quantize(amount_precision, rounding=ROUND_DOWN)
            # Sometime buyer's available balance is very low
            if money_is_zero(matched_amount) or matched_amount < Decimal('0'):
                self._cancel_order(buy)
                self._write_log(f'InsufficientBalance#{buy.id}', end=' ')
                return None
        seller_wallet = sell.src_wallet
        seller_available_balance = seller_wallet.balance - seller_wallet.balance_blocked
        if matched_amount > seller_available_balance:
            matched_amount = seller_available_balance
            if money_is_zero(matched_amount):
                self._cancel_order(sell)
                self._write_log(f'InsufficientBalance#{sell.id}', end=' ')
                return None

        # Here the match parameters are fixed, so we recheck some
        #  criteria that may be missed by other components or may
        #  be affected because of order justifications

        # Guard: Validate match amount and price
        if money_is_zero(matched_price):
            self._cancel_order(sell)
            self._cancel_order(buy)
            self._write_log(f'ZeroPrice#{sell.id}x#{buy.id}', end=' ')
            report_event('FailedMatching: ZeroPrice')
            return None
        if money_is_zero(matched_amount):
            if sell.is_trivial:
                self._cancel_order(sell)
            if buy.is_trivial:
                self._cancel_order(buy)
            msg = f'ZeroAmount#{sell.id}x#{buy.id}'
            self._write_log(msg, end=' ')
            log_event('FailedMatching: ' + msg, level='warning', category='notice', module='market', runner='matcher')
            return None

        # Guard: Check market order price acceptable range
        if buy.is_market and buy.price and matched_price > (Decimal('1') + MARKET_ORDER_MAX_PRICE_DIFF) * buy.price:
            self._cancel_order(buy)
            self._write_log(f'    UnexpectedPrice#{buy.id}-{buy.price:.8f}-{matched_price:.8f}', end=' ')
            return None
        if sell.is_market and sell.price and matched_price < (Decimal('1') - MARKET_ORDER_MAX_PRICE_DIFF) * sell.price:
            self._cancel_order(sell)
            self._write_log(f'    UnexpectedPrice#{sell.id}-{sell.price:.8f}-{matched_price:.8f}', end=' ')
            return None
        self.timer.end_timer('MatchLogic')

        # Fee Calculation
        if self.market_is_buy_in_promotion:
            buy_fee = ZERO
        else:
            buy_user = self.USERS_WITH_MANUAL_FEE.get(buy.user_id)
            buy_fee = UserStatsManager.get_user_fee_by_fields(
                amount=matched_amount,
                is_maker=not is_seller_maker,
                is_usdt=self.market_is_usdt_pair,
                user_vip_level=self.get_user_vip_level(buy.user_id),
                user_fee=buy_user.base_fee if buy_user else None,
                user_fee_usdt=buy_user.base_fee_usdt if buy_user else None,
                user_maker_fee=buy_user.base_maker_fee if buy_user else None,
                user_maker_fee_usdt=buy_user.base_maker_fee_usdt if buy_user else None,
            )
        if self.market_is_sell_in_promotion:
            sell_fee = ZERO
        else:
            sell_user = self.USERS_WITH_MANUAL_FEE.get(sell.user_id)
            sell_fee = UserStatsManager.get_user_fee_by_fields(
                amount=matched_amount * matched_price,
                is_maker=is_seller_maker,
                is_usdt=self.market_is_usdt_pair,
                user_vip_level=self.get_user_vip_level(sell.user_id),
                user_fee=sell_user.base_fee if sell_user else None,
                user_fee_usdt=sell_user.base_fee_usdt if sell_user else None,
                user_maker_fee=sell_user.base_maker_fee if sell_user else None,
                user_maker_fee_usdt=sell_user.base_maker_fee_usdt if sell_user else None,
            )
        self.timer.end_timer('MatchFees')

        # Commit the trade
        # There is a unique constraint on (sell,buy) orders, so
        #  this can throw an IntegrityError which will cause repeated failed matchings.
        #  So we use a (nested) atomic block here to prevent partial trade creation.
        try:
            with transaction.atomic():
                matching = self.create_exchange_transactions(
                    sell,
                    buy,
                    effective_date,
                    matched_amount,
                    matched_price,
                    is_seller_maker,
                    sell_fee,
                    buy_fee,
                )
        except:
            self._write_log(f'Exception#{sell.id}x#{buy.id}', end=' ')
            report_exception()
            return None

        self.update_last_price(matching.matched_price)
        # Returning resulting match object (contains all transactions)
        return matching

    def create_exchange_transactions(
        self,
        sell,
        buy,
        effective_date,
        matched_amount,
        matched_price,
        is_seller_maker,
        sell_fee,
        buy_fee,
    ):
        """Finalize and commit the trade"""
        self._write_log(f'    {sell.pk} x {buy.pk} {matched_amount.normalize():>8,f} {matched_price.normalize():>16,f}')

        # Rial value estimation
        dst_currency = self.market.dst_currency
        total_price = matched_amount * matched_price
        total_price = total_price.quantize(MAX_PRECISION)
        if dst_currency == RIAL:
            rial_value = total_price
        elif dst_currency == TETHER and self.tether_price:
            rial_value = total_price * self.tether_price
        else:
            rial_value = None

        # Trade object creation (OrderMatching)
        matching = OrderMatching.objects.create(
            market=self.market,
            seller_id=sell.user_id,
            sell_order=sell,
            buyer_id=buy.user_id,
            buy_order=buy,
            matched_price=matched_price,
            matched_amount=matched_amount,
            rial_value=rial_value,
            is_seller_maker=is_seller_maker,
            created_at=effective_date,
            sell_fee_amount=sell_fee,
            buy_fee_amount=buy_fee,
        )
        self.timer.end_timer('CreateTrade')

        # Exchange Transactions
        transactions = [
            matching.create_sell_withdraw_transaction(commit=False),
            matching.create_buy_withdraw_transaction(commit=False),
        ]

        # Commiting the match transaction
        if not all(transactions):
            status_str = str([1 if tx else 0 for tx in transactions])
            self._write_log(status_str, end=' ')
            raise MatchingError('Invalid Transactions')
        for tx in transactions:
            tx.commit()
        self.timer.end_timer('TradeTransactions')

        # Committing the trade
        if settings.ASYNC_TRADE_COMMIT:
            self.pending_cache_transactions[f'trade_{matching.id}_txids'] = ','.join(str(tx.id) for tx in transactions)
        else:
            cache.set(f'trade_{matching.id}_txids', ','.join(str(tx.id) for tx in transactions), 1800)

        self.pending_orders_for_update.add(sell)
        self.pending_orders_for_update.add(buy)

        MarketManager.commit_trade(matching)
        self.timer.end_timer('CommitTrade')
        return matching

    def update_last_price(self, new_price):
        # Check for obvious invalid prices
        if not new_price or new_price < MIN_PRICE_PRECISION:
            return
        # Check with order book prices
        lower_bound = self.orderbook_best_buy_price * (1 - PRICE_GUARD_RANGE)
        upper_bound = self.orderbook_best_sell_price * (1 + PRICE_GUARD_RANGE)
        if (lower_bound and new_price < lower_bound) or (upper_bound and new_price > upper_bound):
            self.timer.inc_unexpected_price_metric()
            if not settings.DEBUG:
                Notification.notify_admins(
                    f'Invalid Match Price: {new_price} ∉ ({lower_bound or "-∞"},{upper_bound or "+∞"})\n'
                    f'Best Sell: {self.orderbook_best_buy_price}\n'
                    f'Best Buy: {self.orderbook_best_sell_price}',
                    title=f'‼️ Matcher - {self.market.symbol}',
                    channel='matcher',
                )
            return
        # Set min-max values
        if not self.LAST_PRICE_RANGE:
            self.LAST_PRICE_RANGE.extend((new_price, new_price))
        elif new_price < self.LAST_PRICE_RANGE[0]:
            self.LAST_PRICE_RANGE[0] = new_price
        elif new_price > self.LAST_PRICE_RANGE[-1]:
            self.LAST_PRICE_RANGE[-1] = new_price
        # Set global Tether value
        if self.market.id == self.tether_market_id:
            Matcher.SHARED_TETHER_DATA['price'] = new_price

    @staticmethod
    def validate_price_range(min_price: Decimal, max_price: Decimal) -> bool:
        if min_price > max_price:
            return False
        return not min_price < MIN_PRICE_PRECISION

    def get_market_orders_with_expansion(self, *, is_buy: bool) -> List[Order]:
        """
        Expand current orders by fetching more orders out of the defined range to fill up
        non-trivial orders. is_buy indicates that the order we are going to fill is a buy order
        and we need to fetch more sell orders.
        """

        # Attention! Never lock active orders in any other process outside of matcher.
        # Otherwise, some orders get skipped here which threatens matcher correctness.
        orders_lock_parameters = {'skip_locked': True, 'no_key': True}

        # Log for beta markets.
        with measure_time_cm(
            metric=f'matcher_get_orders_with_expansion__{self.market.symbol}',
        ) if self.market.symbol in MATCHER_GET_ORDER_MONITORING_SYMBOLS else contextlib.nullcontext():
            # Get active orders in this market
            orders = self._get_orders_for_expansion(
                orders_lock_parameters,
                is_buy=is_buy,
            )

        self._write_log(f'(expand) O:{len(orders):<3}')
        self.timer.end_timer('GetOrdersWithExpansion')
        return list(orders)

    def get_market_orders(self):
        # Attention! Never lock active orders in any other process outside of matcher.
        # Otherwise, some orders get skipped here which threatens matcher correctness.
        orders_lock_parameters = {'skip_locked': True, 'no_key': True}

        # Get active orders in this market
        if self.market.symbol in MATCHER_GET_ORDER_MONITORING_SYMBOLS:
            # Log for beta markets.
            with measure_time_cm(metric='matcher_get_orders', labels=(self.market.symbol,)):
                orders = self._get_orders(orders_lock_parameters, self.price_range_high, self.price_range_low)
        else:
            orders = self._get_orders(orders_lock_parameters, self.price_range_high, self.price_range_low)

        # Separate and sort buys and sells
        sells = [order for order in orders if order.is_sell]
        buys = [order for order in orders if order.is_buy]
        sells.sort(key=lambda o: (0 if o.is_market else 1, o.price))
        buys.sort(key=lambda o: (1 if o.is_market else 0, o.price), reverse=True)

        self._write_log(f'S:{len(sells):<3}  B:{len(buys):<3}')
        self.timer.end_timer('GetOrders')
        return sells, buys

    def _get_orders(self, orders_lock_parameters, price_range_high, price_range_low):
        orders = (
            Order.objects.select_for_update(**orders_lock_parameters)
            .filter(
                src_currency=self.market.src_currency,
                dst_currency=self.market.dst_currency,
                status=Order.STATUS.active,
            )
            .defer('description', 'client_order_id')
        )
        use_orderbook_criteria = price_range_low and price_range_high
        if use_orderbook_criteria:
            non_market_orders_filter = ~Q(execution_type__in=Order.MARKET_EXECUTION_TYPES) & (
                Q(order_type=Order.ORDER_TYPES.sell, price__lte=price_range_high)
                | Q(order_type=Order.ORDER_TYPES.buy, price__gte=price_range_low)
            )
            if self._use_orderbook_runtime_limit_logic():
                self.is_orderbook_outdated = (
                    self.orderbook_update_datetime
                    + datetime.timedelta(seconds=self.ORDERBOOK_CRITERIA_AGE_VALIDITY_IN_SECONDS)
                    < timezone.now()
                )
                if not self.is_orderbook_outdated:
                    non_market_orders_filter &= Q(created_at__lte=self.orderbook_update_datetime)
            market_orders_filter = Q(execution_type__in=Order.MARKET_EXECUTION_TYPES)
            orders = orders.filter(non_market_orders_filter | market_orders_filter)
        return list(orders.order_by('created_at'))

    def _get_orders_for_expansion(
        self,
        orders_lock_parameters,
        *,
        is_buy: bool,
    ):
        if (is_buy and self.expansion_sells_len >= self.EXPANSION_THRESHOLD) or (
            not is_buy and self.expansion_buys_len >= self.EXPANSION_THRESHOLD
        ):
            return []

        orders = (
            Order.objects.select_for_update(**orders_lock_parameters)
            .filter(
                src_currency=self.market.src_currency,
                dst_currency=self.market.dst_currency,
                status=Order.STATUS.active,
                order_type=Order.ORDER_TYPES.sell if is_buy else Order.ORDER_TYPES.buy,
            )
            .defer('description', 'client_order_id')
        )

        # in case of not having price range, then there is no expansion.
        if not (self.price_range_low and self.price_range_high):
            return []

        filters = ~Q(execution_type__in=Order.MARKET_EXECUTION_TYPES)

        if is_buy:
            if self.last_expanded_sell_order is None:
                filters = filters & Q(price__gt=self.price_range_high)
            else:
                filters = filters & (
                    Q(price__gt=self.last_expanded_sell_order.price)
                    | (
                        Q(price=self.last_expanded_sell_order.price)
                        & Q(created_at__gt=self.last_expanded_sell_order.created_at)
                    )
                )
        elif self.last_expanded_buy_order is None:
            filters = filters & Q(price__lt=self.price_range_low)
        else:
            filters = filters & (
                Q(price__lt=self.last_expanded_buy_order.price)
                | (
                    Q(price=self.last_expanded_buy_order.price)
                    & Q(created_at__gt=self.last_expanded_buy_order.created_at)
                )
            )

        if (
            self._use_orderbook_runtime_limit_logic()
            and not self.is_orderbook_outdated
        ):
            filters &= Q(created_at__lte=self.orderbook_update_datetime)
        orders = orders.filter(filters)

        if is_buy:
            self.expansion_sells_len += self.EXPANSION_STEP
            self.rounds_of_sells_expansion += 1
            orders = orders.order_by('price', 'created_at')
            q = list(orders[: self.EXPANSION_STEP])
            if len(q) < self.EXPANSION_STEP:
                self.expansion_sells_len = self.EXPANSION_THRESHOLD

            if len(q) > 0:
                self.last_expanded_sell_order = q[-1]
        else:
            self.expansion_buys_len += self.EXPANSION_STEP
            self.rounds_of_buys_expansion += 1
            orders = orders.order_by('-price', 'created_at')
            q = list(orders[: self.EXPANSION_STEP])
            if len(q) < self.EXPANSION_STEP:
                self.expansion_buys_len = self.EXPANSION_THRESHOLD

            if len(q) > 0:
                self.last_expanded_buy_order = q[-1]

        return q

def _activate_stop_orders(market: Market, min_price: Decimal, max_price: Decimal) -> Optional[Iterable[Order]]:
    """Activate any waiting Stop-Loss orders with matching stop price
        based on LAST_PRICE_RANGE.

    Note: Order invalidation (unhandled)
    """
    if not settings.ENABLE_STOP_ORDERS:
        return []

    # Activation Query
    return Order.objects.raw(
        '''UPDATE market_order
        SET status = %(active_status)s, created_at = U0.activated_at
        FROM (
            SELECT
                market_order.id,
                STATEMENT_TIMESTAMP() + ROW_NUMBER() OVER (
                    ORDER BY market_order.created_at
                ) * INTERVAL '1 microseconds' AS activated_at
            FROM market_order
            WHERE (
                market_order.src_currency = %(src_currency)s
                AND market_order.dst_currency = %(dst_currency)s
                AND market_order.execution_type IN %(execution_types)s
                AND market_order.status = %(inactive_status)s
                AND (
                    (market_order.order_type = %(sell_type)s AND market_order.param1 >= %(min_price)s)
                    OR (market_order.order_type = %(buy_type)s AND market_order.param1 <= %(max_price)s)
                )
            )
        ) AS U0
        WHERE U0.id = market_order.id
        RETURNING market_order.*''',
        params={
            'src_currency': market.src_currency,
            'dst_currency': market.dst_currency,
            'active_status': Order.STATUS.active,
            'inactive_status': Order.STATUS.inactive,
            'execution_types': tuple(Order.STOP_EXECUTION_TYPES),
            'sell_type': Order.ORDER_TYPES.sell,
            'buy_type': Order.ORDER_TYPES.buy,
            'min_price': min_price,
            'max_price': max_price,
        },
    )


def _cancel_oco_order_pair(activated_orders: Iterable[Order]) -> Iterable[Order]:
    # Cancel OCO paired limit order
    oco_pair_ids = [order.pair_id for order in activated_orders if order.pair_id]
    if not oco_pair_ids:
        return []

    return Order.objects.raw(
        '''UPDATE market_order
        SET status = %(canceled_status)s
        WHERE (
            execution_type = %(limit_execution)s
            AND id IN %(oco_pair_ids)s
            AND status = %(active_status)s
        )
        RETURNING *''',
        params={
            'active_status': Order.STATUS.active,
            'canceled_status': Order.STATUS.canceled,
            'limit_execution': Order.EXECUTION_TYPES.limit,
            'oco_pair_ids': tuple(oco_pair_ids),
        },
    )


def _update_oco_positions(pair_orders):
    margin_pairs = [order for order in pair_orders if order.is_margin]
    if not margin_pairs:
        return
    MarginOrderChange.objects.bulk_create(MarginOrderChange(order=order) for order in margin_pairs)
    transaction.on_commit(
        partial(task_bulk_update_position_on_order_change.delay, [order.id for order in margin_pairs]),
    )


def _liquidate_positions(market, min_price, max_price):
    task_liquidate_positions.delay(
        market.src_currency,
        market.dst_currency,
        min_price,
        max_price,
    )


def publish_stop_orders_on_websocket(activated_orders, pair_orders):
    orders = list(activated_orders) + list(pair_orders)
    if not activated_orders:
        return
    users_map = User.objects.filter(id__in=[o.user_id for o in orders]).only('id', 'uid').in_bulk()
    order_publish_manager = OrderPublishManager()
    for order in orders:
        order_publish_manager.add_order(order, None, users_map[order.user_id].uid)
    order_publish_manager.publish()


def post_processing_matcher_round(
    market: Market,
    last_price_range: List[Decimal],
    timer: Optional[MarketTimer] = None,
) -> MarketTimer:
    if not timer:
        timer = MarketTimer()
        timer.start_timer()

    if not last_price_range:
        return timer

    # Recheck price range
    min_price, max_price = last_price_range

    if not Matcher.validate_price_range(min_price, max_price):
        Notification.notify_admins(
            f'Invalid StopPrice range: {min_price}-{max_price}',
            title='‼️ Matcher',
            channel='matcher',
        )
        return timer

    activated_orders, pair_orders = [], []
    mark_price = MarkPriceCalculator.get_mark_price(market.src_currency, market.dst_currency)
    if mark_price:
        min_price = max(min_price, mark_price * (1 - STOPLOSS_ACTIVATION_MARK_PRICE_GUARD_RATE))
        max_price = min(max_price, mark_price * (1 + STOPLOSS_ACTIVATION_MARK_PRICE_GUARD_RATE))

    with transaction.atomic():
        activated_orders = _activate_stop_orders(market, min_price, max_price)
        if activated_orders:
            task_notify_stop_order_activation.delay([order.id for order in activated_orders])
            timer.end_timer('StopProcessing')

            pair_orders = _cancel_oco_order_pair(activated_orders)

            if pair_orders:
                timer.end_timer('OCOPairCancel')
                _update_oco_positions(pair_orders)
                timer.end_timer('MarginChangeCreate')
            else:
                timer.end_timer('OCOPairCancel')
        else:
            timer.end_timer('StopProcessing')

    timer.end_timer('StopCommit')

    publish_stop_orders_on_websocket(activated_orders, pair_orders)

    _liquidate_positions(market, min_price, max_price)
    return timer
