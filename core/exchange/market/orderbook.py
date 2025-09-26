import json
import logging
import time
from decimal import Decimal
from itertools import islice
from multiprocessing import Pool
from typing import Any, Callable, Optional
from warnings import warn

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, DecimalField, F, Sum
from django.db.models.functions import Round
from django.utils import timezone
from django.utils.functional import cached_property

from exchange.base.decorators import measure_time, ram_cache
from exchange.base.logging import log_time
from exchange.base.models import AMOUNT_PRECISIONS, PRICE_PRECISIONS, VALID_MARKET_SYMBOLS, Settings
from exchange.base.money import money_is_zero
from exchange.base.publisher import orderbook_publisher
from exchange.base.serializers import normalize_number, serialize_timestamp
from exchange.market.models import Market, Order

logger = logging.getLogger(__name__)


class Timer:
    def __init__(self, callback: Optional[Callable] = None):
        self.callback = callback

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *_):
        self.time = time.time() - self.start
        if callable(self.callback):
            self.callback(self.time)


class OrderBookMetrics:
    orderbook_time_key = 'orderbook_calculation'

    @staticmethod
    def is_disabled():
        if settings.TRADING_MINIMIZE_CACHE_USE:
            return True
        return settings.IS_TEST_RUNNER or Settings.is_disabled('v2_metrics')

    @classmethod
    def set_metrics(cls, duration: int, stage: str, symbol: str, tp: str):
        if cls.is_disabled():
            return
        log_time(cls.orderbook_time_key, int(duration * 1000), labels=(stage, symbol, tp))


class OrderBook:
    MAX_BOOK_ITEMS = 32 if settings.LOAD_LEVEL < 8 else 24

    SMALL_MARKET_SIZE = 50
    MAX_ACTIVE_ORDERS = 75

    def __init__(self, tp, market, max_datetime=None):
        self.tp = tp
        self.market = market
        self.max_datetime = max_datetime or timezone.now()
        if isinstance(self.market, str):
            self.market = Market.by_symbol(self.market)
        self.symbol = self.market.symbol
        with Timer(callback=lambda t: OrderBookMetrics.set_metrics(t, 'query', self.symbol, self.tp)):
            self.orders = self.get_active_orders()
        self.has_match = False
        self.skips = 0

    @classmethod
    def set_max_active_orders(cls, value):
        if value:
            if value < cls.SMALL_MARKET_SIZE:
                warn(f'MAX_ACTIVE_ORDERS ({value}) is less than SMALL_MARKET_SIZE ({cls.SMALL_MARKET_SIZE})')
            cls.MAX_ACTIVE_ORDERS = value

    def _get_active_order_prices(self):
        Round.arity = 2
        ordering = 'price' if self.tp == 'sell' else '-price'
        return (
            Order.objects.filter(
                status=Order.STATUS.active,
                src_currency=self.market.src_currency,
                dst_currency=self.market.dst_currency,
                order_type=getattr(Order.ORDER_TYPES, self.tp),
                created_at__lte=self.max_datetime,
            )
            .exclude(
                execution_type__in=Order.MARKET_EXECUTION_TYPES,
            )
            .values('price')
            .annotate(
                _amount=Round(
                    Sum(F('amount') - F('matched_amount')), self.amount_precision, output_field=DecimalField()
                ),
                _count=Count('*'),
            )
            .order_by(ordering)[: self.MAX_ACTIVE_ORDERS * 2]
        )

    def get_active_orders(self):
        """Unify price precisions and aggregate orders"""
        precision = self.price_precision
        orders = []
        last_order = None
        for order in self._get_active_order_prices():
            price = round(order['price'], precision)
            if not last_order or price != last_order['_price']:
                last_order = {'_price': price, '_amount': order['_amount'], '_count': order['_count']}
                orders.append(last_order)
            else:
                last_order['_amount'] += order['_amount']
                last_order['_count'] += order['_count']
        return orders

    @property
    def price_precision(self):
        return -PRICE_PRECISIONS.get(self.symbol, Decimal('1e-2')).adjusted()

    @property
    def amount_precision(self):
        return -AMOUNT_PRECISIONS.get(self.symbol, Decimal('1e-8')).adjusted()

    @cached_property
    def best_price(self):
        return self.orders[0]['_price'] if self.orders else None

    @cached_property
    def book_orders(self):
        orders = []
        for order in islice(self.orders, self.skips, None):
            if not money_is_zero(order['_amount']):
                orders.append(order)
                if len(orders) >= self.MAX_ACTIVE_ORDERS:
                    break
        return orders

    @cached_property
    def best_active_price(self):
        return self.book_orders[0]['_price'] if self.book_orders else None

    @cached_property
    def last_active_price(self):
        total = 0
        order = None
        for order in self.book_orders:
            total += order['_count']
            if total >= self.MAX_ACTIVE_ORDERS:
                break
        if total >= self.SMALL_MARKET_SIZE:
            return order['_price']
        return None

    @cached_property
    def last_skipped_price(self):
        return self.orders[max(self.skips - 1, 0)]['_price'] if self.has_match else None

    @cached_property
    def public_book_orders(self):
        return [
            [normalize_number(order['_price']), normalize_number(order['_amount'])]
            for order in self.book_orders[: self.MAX_BOOK_ITEMS]
        ]


class OrderBookGenerator:
    CACHE_TIMEOUT = None if settings.DEBUG else 15 * 60

    all_orderbooks = {}
    cache_update_times = {}

    _cache_values = {}

    @classmethod
    @measure_time(metric='orderbook_round')
    def run(cls, pool: Optional[Pool] = None):
        markets = [market for symbol in VALID_MARKET_SYMBOLS if (market := cls._get_market(symbol)) is not None]
        if pool:
            results = pool.map(cls.create_market_orderbooks, markets)
        else:
            results = [cls.create_market_orderbooks(market) for market in markets]
        total_orders = sum(result[0] for result in results if result)
        total_skips = sum(result[1] for result in results if result)
        return f'Orderbooks={len(cls.all_orderbooks)} Orders={total_orders} Skips={total_skips}'

    @staticmethod
    @ram_cache(timeout=60)
    def _get_market(symbol) -> Optional[Market]:
        market = Market.by_symbol(symbol)
        if not market:
            print(f'Cannot get market for symbol "{symbol}".')
        return market

    @classmethod
    def create_market_orderbooks(cls, market: Market) -> Optional[tuple]:
        with Timer(callback=lambda t: OrderBookMetrics.set_metrics(t, 'create', market.symbol, 'all')):
            update_time = timezone.now()
            update_timestamp = serialize_timestamp(update_time)
            sell_book = OrderBook('sell', market, update_time)
            buy_book = OrderBook('buy', market, update_time)
            cls.skip_order_matches(sell_book, buy_book)

            total_orders = len(sell_book.orders) + len(buy_book.orders)
            total_skips = sell_book.skips + buy_book.skips

            last_trade_price = cls.get_last_trade_price(market)

            prev_book = cls.all_orderbooks.get(market.symbol, {})
            cls._cache_values.clear()
            cls.cache_market_values(
                market.symbol,
                total_skips,
                update_timestamp,
                last_trade_price,
                prev_book,
            )
            for book in (sell_book, buy_book):
                cls.cache_orderbook_values(book, prev_book)
            cache.set_many(cls._cache_values, cls.CACHE_TIMEOUT)
            values = (
                market.symbol,
                sell_book.public_book_orders,
                buy_book.public_book_orders,
                update_timestamp,
                last_trade_price,
            )
            cls.publish_to_ws(values, prev_book)
            cls.update_all_orderbooks(values)
            return total_orders, total_skips

    @classmethod
    def get_depth_chart_orderbook_for_market(cls, market_symbol: str):
        from exchange.market.depth_chart import DepthChartOrderBook

        market = Market.by_symbol(market_symbol)
        if not market:
            logger.warning(f'Cannot get market for symbol "{market_symbol}".')
            return 0, 0, [], [], '0'
        sell_book = DepthChartOrderBook('sell', market)
        buy_book = DepthChartOrderBook('buy', market)
        cls.skip_order_matches(sell_book, buy_book)
        total_orders = len(sell_book.orders) + len(buy_book.orders)
        total_skips = sell_book.skips + buy_book.skips
        last_trade_price = cls.get_last_trade_price(market)
        return total_orders, total_skips, sell_book.public_book_orders, buy_book.public_book_orders, last_trade_price

    @classmethod
    def skip_order_matches(cls, sell_book, buy_book):
        """Skip upcoming orders matching to correct unmatched values"""
        matched = False
        i, j = 0, 0
        try:
            for i, sell_order in enumerate(sell_book.orders):
                while j < len(buy_book.orders) and sell_order['_amount']:
                    buy_order = buy_book.orders[j]
                    if buy_order['_price'] < sell_order['_price']:
                        raise StopIteration
                    matched = True
                    amount = min(buy_order['_amount'], sell_order['_amount'])
                    sell_order['_amount'] -= amount
                    buy_order['_amount'] -= amount
                    j += not buy_order['_amount']
                if j == len(buy_book.orders):
                    i += not sell_order['_amount']
                    raise StopIteration
        except StopIteration:
            pass
        finally:
            for book, skips in ((sell_book, i), (buy_book, j)):
                book.has_match = matched
                book.skips = skips

    @staticmethod
    def get_last_trade_price(market):
        return normalize_number(market.get_last_trade_price() or '')

    @classmethod
    def cache_orderbook_values(cls, book: OrderBook, prev_book: dict):
        # Bids and asks are actually used wrong here. Bids correspond to buy orders and asks to sell orders.
        # This format is still maintained for the sake of backward compatibility.
        side = 'bids' if book.tp == 'sell' else 'asks'
        symbol = book.market.symbol
        cls._set_cache_if_obsolete(f'orderbook_{symbol}_{side}', book.public_book_orders, prev_book.get(side))
        cls._set_cache(f'orderbook_{symbol}_best_{book.tp}', book.best_price)
        cls._set_cache(f'orderbook_{symbol}_best_active_{book.tp}', book.best_active_price)
        cls._set_cache(f'orderbook_{symbol}_last_active_{book.tp}', book.last_active_price)

    @classmethod
    def cache_market_values(
        cls,
        symbol: str,
        skips: int,
        update_time: int,
        last_trade_price: str,
        prev_book: dict,
    ):
        cls._set_cache(f'orderbook_{symbol}_skips', skips)
        cls._set_cache(f'orderbook_{symbol}_update_time', str(update_time))
        cls._set_cache_if_obsolete(
            f'orderbook_{symbol}_last_trade_price', last_trade_price, prev_book.get('lastTradePrice')
        )

    @classmethod
    def _set_cache(cls, key: str, value: Any):
        if isinstance(value, (list, dict)):
            value = json.dumps(value, separators=(',', ':'))
        cls._cache_values[key] = value

    @classmethod
    def _set_cache_if_obsolete(cls, cache_key: str, value: Any, prev_value: Any):
        update_time = int(time.time())
        time_passed = update_time - cls.cache_update_times.get(cache_key, 0)
        is_cache_expired = cls.CACHE_TIMEOUT and (time_passed > cls.CACHE_TIMEOUT - 10)
        if prev_value != value or is_cache_expired:
            cls._set_cache(cache_key, value)
            cls.cache_update_times[cache_key] = update_time

    @classmethod
    def publish_to_ws(cls, orderbook_values, prev_orderbook):
        if not orderbook_values:
            return
        symbol, sells, buys, update_time, last_trade_price = orderbook_values
        if (
            prev_orderbook
            and prev_orderbook['bids'] == sells
            and prev_orderbook['asks'] == buys
            and prev_orderbook['lastTradePrice'] == last_trade_price
        ):
            return
        orderbook_publisher(symbol, update_time, last_trade_price, sells, buys)

    @classmethod
    def update_all_orderbooks(cls, orderbook_values: tuple):
        symbol, bids, asks, update_time, last_trade = orderbook_values
        cls.all_orderbooks[symbol] = {
            'lastUpdate': update_time,
            'lastTradePrice': last_trade,
            'bids': bids,
            'asks': asks,
        }
