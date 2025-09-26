import bisect
import datetime
import time
from decimal import Decimal
from functools import lru_cache
from typing import ClassVar, Dict, Iterable, List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache, caches
from django.db.models import Case, DateTimeField, Exists, F, Max, Min, OuterRef, QuerySet, Sum, Value, When, Window
from django.db.models.functions import FirstValue, Greatest, Least
from django.utils import timezone

from exchange.base.decorators import measure_time
from exchange.base.logging import report_exception
from exchange.base.models import AVAILABLE_MARKETS, PRICE_PRECISIONS, Currencies
from exchange.base.publisher import candles_publisher
from exchange.market.models import Market, MarketCandle, Order, OrderMatching


def gateway_exchange_amount(market, price):
    amount = get_exchange_amount_from_price(market, price)
    if not amount:
        return None
    return amount * Decimal(1.01)


def get_exchange_amount_from_price(market, price):
    if not market:
        return None
    if price <= 0:
        return None
    orders = Order.get_active_market_orders(market.src_currency, market.dst_currency)
    buy_orders = orders.filter(order_type=Order.ORDER_TYPES.buy).order_by('-price')
    if not buy_orders:
        return None
    total_coin = Decimal(0.0)
    total_price = Decimal(0.0)
    for order in buy_orders:
        temp = total_price + order.unmatched_total_price
        if temp >= price:
            total_coin += Decimal((price - total_price) / order.price)
            return total_coin

        total_coin += order.unmatched_amount
        total_price += order.unmatched_total_price
    return None


def get_orders_stats(market, current=True, date_from=None, date_to=None):
    if current:
        return {
            'bestSell': cache.get(f'orderbook_{market.symbol}_best_active_sell') or Decimal('0'),
            'bestBuy': cache.get(f'orderbook_{market.symbol}_best_active_buy') or Decimal('0'),
        }

    orders = Order.get_all_market_orders(market.src_currency, market.dst_currency, date_from=date_from, date_to=date_to)
    sell_orders = orders.filter(order_type=Order.ORDER_TYPES.sell).order_by('created_at')
    buy_orders = orders.filter(order_type=Order.ORDER_TYPES.buy).order_by('created_at')
    sell_orders = sell_orders.aggregate(best=Min('price'))
    buy_orders = buy_orders.aggregate(best=Max('price'))
    return {
        'bestSell': sell_orders['best'] or Decimal('0'),
        'bestBuy': buy_orders['best'] or Decimal('0'),
    }


class MarketCandlesBaseCache:
    CACHE_SIZE: int

    @classmethod
    def cache(cls):
        return caches['default']

    @classmethod
    def get_cache_key(cls, market: Market, resolution: int, postfix: str) -> str:
        resolution_key = MarketCandle.get_resolution_key(resolution)
        return f'marketdata_{market.symbol}_{resolution_key}_{postfix}'

    @classmethod
    def get_candle_cache_key(cls, candle: MarketCandle) -> str:
        return cls.get_cache_key(
            candle.market, candle.resolution, cls.get_postfix(candle.start_time, candle.resolution)
        )

    @classmethod
    def update_cache(cls, candles: list):
        candle_buckets = cls.get_candle_buckets(candles)
        for bucket_candles in candle_buckets:
            lead_candle = bucket_candles[0]
            cache_key = cls.get_candle_cache_key(lead_candle)
            cached_data = cls.cache().get(cache_key)
            if cached_data and lead_candle.timestamp in cached_data['time']:
                new_data = cls.encode_for_cache(bucket_candles)
                from_index = cached_data['time'].index(new_data['time'][0])
                cache_data = {
                    field: (cached_data[field][:from_index] + new_data[field])[-cls.CACHE_SIZE:]
                    for field in cached_data
                }
                cls.cache().set(cache_key, cache_data, timeout=cls.get_timeout(lead_candle))
            else:
                cls.initialize_data(lead_candle.market, lead_candle.resolution)

    @classmethod
    def encode_for_cache(cls, candles: list) -> dict:
        cache_fields = {
            'time': lambda c: c.timestamp,
            'open': lambda c: float(c.public_open_price),
            'high': lambda c: float(c.public_high_price),
            'low': lambda c: float(c.public_low_price),
            'close': lambda c: float(c.public_close_price),
            'volume': lambda c: float(c.trade_amount),
        }
        return {name: [get_value(candle) for candle in candles] for name, get_value in cache_fields.items()}

    @classmethod
    def get_postfix(cls, start_time: datetime.datetime, resolution: int) -> str:
        raise NotImplementedError()

    @classmethod
    def get_timeout(cls, candle: MarketCandle) -> Optional[int]:
        raise NotImplementedError()

    @classmethod
    def get_candle_buckets(cls, candles: list) -> list:
        raise NotImplementedError()

    @classmethod
    def initialize_data(cls, market: Market, resolution: int):
        raise NotImplementedError()

    @classmethod
    def clear_cache(cls, market: Market, resolution: int, since: Optional[timezone.datetime] = None):
        raise NotImplementedError()

    @classmethod
    def get_cache_candle(cls, market, resolution, start_time):
        candle = MarketCandle(market=market, resolution=resolution, start_time=start_time)
        cache_key = cls.get_candle_cache_key(candle)
        cached_data = cls.cache().get(cache_key)
        if cached_data and candle.timestamp in cached_data['time']:
            i = cached_data['time'].index(candle.timestamp)
            candle.open_price = Decimal(str(cached_data['open'][i]))
            candle.high_price = Decimal(str(cached_data['high'][i]))
            candle.low_price = Decimal(str(cached_data['low'][i]))
            candle.close_price = Decimal(str(cached_data['close'][i]))
            candle.trade_amount = Decimal(str(cached_data['volume'][i]))
            return candle
        return None


class ShortTermCandlesCache(MarketCandlesBaseCache):
    CACHE_SIZE: int = 10

    @classmethod
    def get_postfix(cls, *args, **kwargs) -> str:
        return 'short'

    @classmethod
    def get_timeout(cls, candle: MarketCandle) -> int:
        return int(candle.duration.total_seconds() * 2)

    @classmethod
    def get_candle_buckets(cls, candles: list) -> list:
        if candles:
            return [candles]
        return []

    @classmethod
    def initialize_data(cls, market: Market, resolution: int):
        candles = list(
            reversed(
                MarketCandle.objects.filter(market=market, resolution=resolution).order_by(
                    '-start_time'
                )[: cls.CACHE_SIZE]
            )
        )
        cache_key = cls.get_cache_key(market, resolution, cls.get_postfix())
        cache_data = cls.encode_for_cache(candles)
        cls.cache().set(cache_key, cache_data, timeout=candles[0].duration.total_seconds() * 2)

    @classmethod
    def clear_cache(cls, market: Market, resolution: int, since: Optional[timezone.datetime] = None):
        cache_key = cls.get_cache_key(market, resolution, cls.get_postfix())
        cls.cache().delete(cache_key)


class LongTermCandlesCache(MarketCandlesBaseCache):
    CACHE_SIZE: int = 200
    KEEP_HISTORY_FOR_DAYS: int = (7 if settings.IS_PROD else 90) * 86400

    @classmethod
    @lru_cache(maxsize=len(AVAILABLE_MARKETS) * 2)
    def get_bucket(cls, start_time: datetime.datetime, resolution: int) -> (int, int):
        duration = MarketCandle.resolution_to_timedelta(resolution).total_seconds()
        bucket_length = cls.CACHE_SIZE * duration
        timestamp = start_time.timestamp()
        start = timestamp - timestamp % bucket_length
        end = start + bucket_length
        return int(start), int(end)


    @classmethod
    def get_postfix(cls, start_time: datetime.datetime, resolution: int) -> str:
        start, _ = cls.get_bucket(start_time, resolution)
        return str(start)

    @classmethod
    def _calculate_timeout(cls, resolution: int, start_time: int) -> Optional[int]:
        if resolution != MarketCandle.RESOLUTIONS.minute:
            return None
        current_timestamp = int(timezone.now().timestamp())
        return max(cls.KEEP_HISTORY_FOR_DAYS - (current_timestamp - start_time), 0)

    @classmethod
    def get_timeout(cls, candle: MarketCandle = None) -> Optional[int]:
        bucket_start_time, _ = cls.get_bucket(candle.start_time, candle.resolution)
        return cls._calculate_timeout(candle.resolution, bucket_start_time)

    @classmethod
    def get_candle_buckets(cls, candles: list) -> list:
        next_bucket = 0
        candle_buckets = []
        for candle in candles:
            if candle.timestamp >= next_bucket:
                _, next_bucket = cls.get_bucket(candle.start_time, candle.resolution)
                candle_buckets.append([])
            candle_buckets[-1].append(candle)
        return candle_buckets

    @classmethod
    def initialize_data(cls, market: Market, resolution: int):
        from exchange.market.tasks import init_candles_cache
        time_range = MarketCandle.objects.filter(market=market, resolution=resolution).aggregate(
            start=Min('start_time'),
            end=Max('start_time'),
        )
        if not any(time_range.values()):
            return
        start_bucket, _ = cls.get_bucket(time_range['start'], resolution)
        end_bucket, next_bucket = cls.get_bucket(time_range['end'], resolution)
        cls.save_bucket_data(market, resolution, end_bucket, next_bucket)
        bucket_length = next_bucket - end_bucket
        init_candles_cache.delay(market.symbol, resolution, start_bucket, end_bucket, bucket_length)

    @classmethod
    def save_bucket_data(cls, market: Market, resolution: int, bucket: int, next_bucket: int) -> bool:
        timeout = cls._calculate_timeout(resolution, bucket)
        if timeout and timeout < 0:
            return False
        cache_key = cls.get_cache_key(market, resolution, str(bucket))
        cached_data = cls.cache().get(cache_key)
        if cached_data and len(cached_data['time']) == cls.CACHE_SIZE:
            return False
        candles = list(
            MarketCandle.objects.filter(
                market=market,
                resolution=resolution,
                start_time__gte=timezone.datetime.fromtimestamp(bucket).astimezone(),
                start_time__lt=timezone.datetime.fromtimestamp(next_bucket).astimezone(),
            ).order_by('start_time')
        )
        if not candles:
            return False
        cls.cache().set(cache_key, cls.encode_for_cache(candles), timeout=timeout)
        return True

    @classmethod
    def clear_cache(cls, market: Market, resolution: int, since: Optional[timezone.datetime] = None):
        current_timestamp = timezone.now().timestamp()
        if not since:
            first_candle = (
                MarketCandle.objects.filter(
                    market=market,
                    resolution=resolution,
                )
                .order_by('start_time')
                .first()
            )
            if not first_candle:
                return
            since = first_candle.start_time
        bucket, next_bucket = cls.get_bucket(since, resolution)
        bucket_length = next_bucket - bucket
        while bucket < current_timestamp:
            cache_key = cls.get_cache_key(market, resolution, str(bucket))
            cls.cache().delete(cache_key)
            bucket += bucket_length


class ShortTermCandlesCacheChartAPI(ShortTermCandlesCache):
    @classmethod
    def cache(cls):
        return caches['chart_api']


class LongTermCandlesCacheChartAPI(LongTermCandlesCache):
    KEEP_HISTORY_FOR_DAYS: int = (90 if settings.IS_PROD else 365) * 86400

    @classmethod
    def cache(cls):
        return caches['chart_api']


class UpdateMarketCandles:
    MINUTES_TO_RECALCULATE: int = 5
    CACHES: tuple = (
        ShortTermCandlesCache,
        LongTermCandlesCache,
        ShortTermCandlesCacheChartAPI,
        LongTermCandlesCacheChartAPI,
    )
    READ_DB: str = 'replica' if 'replica' in settings.DATABASES else 'default'

    # tuple of (market_id, resolution, start_time) -> candle_data
    previous_round_data: Dict[Tuple[int, int, datetime.datetime], Dict] = {}
    current_round_data: Dict[Tuple[int, int, datetime.datetime], Dict] = {}

    @classmethod
    @measure_time(metric='market_candles')
    def run(cls, dt: Optional[datetime.datetime] = None) -> str:
        cls.current_round_data = {}
        dt = dt or timezone.now()
        has_trade = Exists(OrderMatching.objects.filter(market_id=OuterRef('id')).only('market_id'))
        markets = list(
            Market.get_active_markets().using(cls.READ_DB).annotate(has_trade=has_trade).exclude(has_trade=False),
        )
        times = [(dt - datetime.timedelta(minutes=i)).astimezone() for i in reversed(range(cls.MINUTES_TO_RECALCULATE))]
        resolution_times_list = []
        for resolution, _ in MarketCandle.RESOLUTIONS:
            resolution: int
            if resolution > MarketCandle.RESOLUTIONS.minute:
                resolution_key = MarketCandle.get_resolution_key(resolution)
                times = [times[0], times[-1]]
                if getattr(times[1], resolution_key) == getattr(times[0], resolution_key):
                    times.pop()
            cls.update_resolution_candles(markets, resolution, times)
            resolution_times_list.append((resolution, times))

        to_be_published_data = cls.get_to_be_published_data(markets, resolution_times_list)

        cls.previous_round_data = cls.current_round_data
        cls.publish_candles(to_be_published_data)
        return f'MarketCandles: markets={len(markets)}'

    @classmethod
    def get_to_be_published_data(
        cls, markets: List[Market], resolution_dts: List[Tuple[int, List[datetime.datetime]]]
    ) -> Dict[Tuple[Market, int], List]:
        result = {}
        for market in markets:
            for resolution, dts in resolution_dts:
                result[(market, resolution)] = []
                for dt in dts[:-1]:
                    start_time = MarketCandle.get_start_time(dt, resolution)
                    key = (market.id, resolution, start_time)
                    if cls.current_round_data.get(key) != cls.previous_round_data.get(key):
                        result[(market, resolution)].append(dt)
                result[(market, resolution)].append(dts[-1])

        return result

    @classmethod
    def publish_candles(cls, market_resolution_to_dts: Dict[Tuple[Market, int], List[datetime.datetime]]):
        candle_publisher = CandlePublisher(market_resolution_to_dts)
        try:
            candle_publisher.publish()
        except Exception:
            report_exception()

    @classmethod
    def update_resolution_candles(cls, markets: Iterable, resolution: int, dt_s: list):
        candles_dict = cls.update_time_candles(markets, resolution, dt_s)
        cls.update_current_round_data(resolution, candles_dict)

        cls.update_caches(candles_dict)

    @classmethod
    @lru_cache(maxsize=len(AVAILABLE_MARKETS) * 3)
    def get_last_candle_before(
        cls,
        market: Market,
        resolution: int,
        start_time: datetime.datetime,
    ) -> Optional[MarketCandle]:
        last_start_time = MarketCandle.get_start_time(start_time - timezone.timedelta(seconds=1), resolution)
        return MarketCandle.get_candle(market, resolution, last_start_time)

    @classmethod
    @lru_cache(maxsize=len(AVAILABLE_MARKETS))
    def get_last_trade_price(cls, market: Market, start_time: datetime.datetime) -> Decimal:
        try:
            max_backward_search_delta = timezone.timedelta(days=7)
            last_trade = (
                OrderMatching.objects.using(cls.READ_DB)
                .filter(
                    market=market,
                    created_at__lt=start_time,
                    created_at__gt=start_time - max_backward_search_delta,
                )
                .latest('created_at')
            )
        except OrderMatching.DoesNotExist:
            return Decimal(0)
        else:
            return last_trade.matched_price

    @classmethod
    def get_last_close_price(
        cls,
        market: Market,
        resolution: int,
        start_time: datetime.datetime,
        last_candle: MarketCandle,
    ) -> Decimal:
        if not last_candle:
            last_candle = cls.get_last_candle_before(market, resolution, start_time)
        if last_candle:
            return last_candle.close_price
        return cls.get_last_trade_price(market, start_time)

    @classmethod
    def update_current_round_data(cls, resolution: int, candles: Dict[Market, List[MarketCandle]]):
        for _, candles in candles.items():
            for candle in candles:
                key = (candle.market_id, resolution, candle.start_time)
                cls.current_round_data[key] = {
                    'market_id': candle.market_id,
                    'open_price': candle.open_price,
                    'high_price': candle.high_price,
                    'low_price': candle.low_price,
                    'close_price': candle.close_price,
                    'trade_amount': candle.trade_amount,
                    'trade_total': candle.trade_total,
                }

    @classmethod
    def update_time_candles(
        cls,
        markets: Iterable,
        resolution: int,
        dt_s: List[datetime.datetime],
        *,
        force_base_mode: bool = False,
    ) -> dict:
        start_times = [MarketCandle.get_start_time(dt, resolution) for dt in dt_s]
        candles_data = cls._get_candles_data(
            resolution=resolution, start_times=start_times, force_base_mode=force_base_mode
        )

        candles = cls._create_or_update_candles(markets, resolution, start_times, candles_data)
        updated_candles = {market: [] for market in markets}
        for candle in candles:
            updated_candles[candle.market].append(candle)
        return updated_candles

    @classmethod
    def _create_or_update_candles(
        cls,
        markets: Iterable,
        resolution: int,
        start_times: List[datetime.datetime],
        candles_data: dict,
    ) -> list:
        last_candles = {}
        updated_candles = []
        all_candles = []
        update_fields = ('open_price', 'high_price', 'low_price', 'close_price', 'trade_amount', 'trade_total')
        for market in markets:
            for start_time in start_times:
                candle_data = candles_data.get((market.id, start_time)) or cls._get_default_candle_data(
                    market,
                    resolution=resolution,
                    start_time=start_time,
                    last_candle=last_candles.get(market),
                )

                old_candle_data = cls.previous_round_data.get((market.id, resolution, start_time))
                if candle_data:
                    candle_data.pop('bucket', None)
                    candle_obj = MarketCandle(
                        resolution=resolution, start_time=start_time, market=market, **candle_data
                    )
                    all_candles.append(candle_obj)
                    last_candles[market] = candle_obj
                    if old_candle_data != candle_data:
                        updated_candles.append(candle_obj)

        MarketCandle.objects.bulk_create(
            updated_candles,
            update_fields=update_fields,
            update_conflicts=True,
            unique_fields=('resolution', 'start_time', 'market'),
        )
        return all_candles

    @classmethod
    def _get_default_candle_data(
        cls,
        market: Market,
        resolution: int,
        start_time: datetime.datetime,
        last_candle: MarketCandle,
    ) -> Optional[dict]:
        default_price = cls.get_last_close_price(market, resolution, start_time, last_candle=last_candle)
        if not default_price:
            return None
        price_fields = ('open_price', 'close_price', 'high_price', 'low_price')
        candle_data = {price_field: default_price for price_field in price_fields}
        candle_data['market_id'] = market.id
        return candle_data

    @classmethod
    def _get_candles_data(cls, resolution: int, start_times: List[datetime.datetime], *, force_base_mode: bool) -> dict:
        if resolution == MarketCandle.RESOLUTIONS.minute or force_base_mode:
            candles_data = cls._get_base_candles_data(resolution, start_times)
        else:
            candles_data = cls._get_compound_candles_data(resolution, start_times)
        return {(data['market_id'], data['bucket']): data for data in candles_data}

    @classmethod
    def _get_base_candles_data(cls, resolution: int, start_times: List[datetime.datetime]) -> QuerySet:
        criteria = []
        for start_time in start_times:
            end_time = MarketCandle.get_end_time(start_time, resolution)
            criteria.append(When(created_at__gte=start_time, created_at__lte=end_time, then=Value(start_time)))
        bucket_case = Case(*criteria, default=Value(None), output_field=DateTimeField())
        window = dict(partition_by=('market_id', 'bucket'))
        first_start_time = min(start_times)
        last_end_time = MarketCandle.get_end_time(max(start_times), resolution)
        return (
            OrderMatching.objects.using(cls.READ_DB)
            .filter(created_at__gte=first_start_time, created_at__lte=last_end_time)
            .annotate(bucket=bucket_case)
            .filter(
                bucket__isnull=False,
                matched_amount__gt=0,  # Excluding reversed trades
            )
            .values('market_id', 'bucket')
            .distinct()
            .annotate(
                open_price=Window(FirstValue('matched_price'), order_by=('id',), **window),
                high_price=Window(Max('matched_price'), **window),
                low_price=Window(Min('matched_price'), **window),
                close_price=Window(FirstValue('matched_price'), order_by=('-id',), **window),
                trade_amount=Window(Sum('matched_amount'), **window),
                trade_total=Window(Sum(F('matched_amount') * F('matched_price')), **window),
            )
        )

    @classmethod
    def _get_compound_candles_data(cls, resolution: int, start_times: List[datetime.datetime]) -> QuerySet:
        criteria = []
        for start_time in start_times:
            end_time = MarketCandle.get_end_time(start_time, resolution)
            criteria.append(When(start_time__gte=start_time, start_time__lte=end_time, then=Value(start_time)))
        bucket_case = Case(*criteria, default=Value(None), output_field=DateTimeField())

        base_resolution = resolution - 1
        window = dict(partition_by=('market_id', 'bucket'))

        first_start_time = min(start_times)
        last_end_time = MarketCandle.get_end_time(max(start_times), resolution)

        return (
            MarketCandle.objects.filter(start_time__gte=first_start_time, start_time__lte=last_end_time)
            .annotate(bucket=bucket_case)
            .filter(
                resolution=base_resolution,
                bucket__isnull=False,
                trade_amount__gt=0,
            )
            .values('market_id', 'bucket')
            .distinct()
            .annotate(
                open_price=Window(FirstValue('open_price'), order_by=('start_time',), **window),
                high_price=Window(Max('high_price'), **window),
                low_price=Window(Min('low_price'), **window),
                close_price=Window(FirstValue('close_price'), order_by=F('start_time').desc(), **window),
                trade_amount=Window(Sum('trade_amount'), **window),
                trade_total=Window(Sum('trade_total'), **window),
            )
        )

    @classmethod
    def update_caches(cls, updated_candles: dict):
        for candles in updated_candles.values():
            for cache_layer in cls.CACHES:
                cache_layer.update_cache(candles)

    @classmethod
    def clear_caches(cls, markets: Iterable, resolution: int, since: Optional[timezone.datetime] = None):
        for market in markets:
            for cache_layer in cls.CACHES:
                cache_layer.clear_cache(market, resolution, since)




def get_markets_last_price_range(since: datetime.datetime, *, exact: bool = False) -> QuerySet:
    """Get markets last price range

    Args:
        since: the point of time to get changes afterward
        exact: use trades if exact data is vital othervise candles

    Returns: A QuerySet with tuples of market's src and dst currency, along with high and low prices
    """
    if exact:
        queryset = (
            OrderMatching.objects.filter(
                created_at__gte=since,
                matched_amount__gt=0,  # Excluding reversed trades
            )
            .values('market')
            .annotate(
                market_high_price=Max('matched_price'),
                market_low_price=Min('matched_price'),
                last_time=Max('created_at'),
            )
        )
    else:
        resolution = MarketCandle.RESOLUTIONS.minute
        queryset = (
            MarketCandle.objects.filter(
                resolution=resolution,
                start_time__gte=MarketCandle.get_start_time(since, resolution),
            )
            .values('market')
            .annotate(
                market_high_price=Max(Least('price_upper_bound', 'high_price')),
                market_low_price=Min(Greatest('price_lower_bound', 'low_price')),
                volume=Sum('trade_amount'),
                last_time=Max('start_time'),
            )
            .exclude(volume=0)
        )
    return queryset.values_list(
        'market__src_currency',
        'market__dst_currency',
        'market_high_price',
        'market_low_price',
        'last_time',
    )


class CandlePublisher:

    RESOLUTION_GROUPS: ClassVar[Dict[str, Dict[str, int]]] = {
        'minute': {'1': 1, '5': 5, '15': 15, '30': 30},
        'hour': {'60': 1, '180': 3, '240': 4, '360': 6, '720': 12},
        'day': {'D': 1, '1D': 1, '2D': 2, '3D': 3},
    }

    CACHE_FIELDS = ('time', 'open', 'high', 'low', 'close', 'volume')

    def __init__(self, market_resolution_to_dts: Dict[Tuple[Market, int], List[datetime.datetime]]) -> None:
        self.market_resolution_to_dts = market_resolution_to_dts

    @staticmethod
    def get_start_of_candle_by_factor(dt: datetime.datetime, primary_resolution: int, factor: int) -> int:

        timeframe = int(MarketCandle.resolution_to_timedelta(primary_resolution).total_seconds()) * factor
        timestamp = int(dt.timestamp())

        result = timestamp - (timestamp + time.localtime(timestamp).tm_gmtoff) % timeframe
        if result - timestamp > 3600:
            fixed_result = result + (time.localtime(timestamp).tm_isdst - time.localtime(result).tm_isdst) * 3600
            if time.localtime(fixed_result).tm_isdst == time.localtime(result).tm_isdst:
                return fixed_result
        return result


    @staticmethod
    def add_short_term_cache_key(market, primary_resolution, cache_key_map) -> Dict[str, Tuple[str, int]]:

        cache_key = ShortTermCandlesCache.get_cache_key(market, primary_resolution, ShortTermCandlesCache.get_postfix())
        cache_key_map[cache_key] = (market.symbol, primary_resolution)

        return cache_key_map

    def add_long_term_cache_key(
        self,
        market: Market,
        dts: List[datetime.datetime],
        primary_resolution: int,
        cache_key_map: Dict[str, Tuple[str, int]],
        resolutions: List[int],
    ):

        primary_candle_duration = int(MarketCandle.resolution_to_timedelta(primary_resolution).total_seconds())

        bucket_length = LongTermCandlesCache.CACHE_SIZE * primary_candle_duration

        start_time = MarketCandle.get_start_time(dts[-1], primary_resolution)
        start_of_bucket, _ = LongTermCandlesCache.get_bucket(start_time, primary_resolution)
        earliest_start_of_candle = min(
            [self.get_start_of_candle_by_factor(dts[0], primary_resolution, r) for r in resolutions]
        )

        cache_key = LongTermCandlesCache.get_cache_key(market, primary_resolution, start_of_bucket)
        cache_key_map[cache_key] = (market.symbol, primary_resolution)

        while earliest_start_of_candle < start_of_bucket:
            start_of_bucket -= bucket_length
            cache_key = LongTermCandlesCache.get_cache_key(market, primary_resolution, start_of_bucket)
            cache_key_map[cache_key] = (market.symbol, primary_resolution)

        return cache_key_map


    def generate_cache_keys(self) -> Dict[str, Tuple[str, int]]:
        cache_key_map: Dict[str, Tuple[str, int]] = {}

        for (market, primary_resolution), dts in self.market_resolution_to_dts.items():
            resolution_key = MarketCandle.get_resolution_key(primary_resolution)

            secondary_resolutions = list(CandlePublisher.RESOLUTION_GROUPS[resolution_key].values())
            max_resolution_factor = max(secondary_resolutions)

            count_back = (dts[-1] - dts[0]) / MarketCandle.resolution_to_timedelta(primary_resolution)
            if count_back + max_resolution_factor < ShortTermCandlesCache.CACHE_SIZE:
                cache_key_map = self.add_short_term_cache_key(market, primary_resolution, cache_key_map)
            else:
                cache_key_map = self.add_long_term_cache_key(
                    market, dts, primary_resolution, cache_key_map, secondary_resolutions
                )

        return cache_key_map

    @staticmethod
    def extend_cache_slices(cache_key_map: Dict[str, Tuple[str, int]], cache_data: Dict[str, Dict]) -> Dict[
        Tuple[str, int], Dict[str, List]]:

        time_frames: Dict[Tuple[str, int], Dict[str, List]] = {}

        for key, slice_of_data in sorted(cache_data.items(), key=lambda item: item[1]['time'][0]):
            market_symbol, resolution = cache_key_map[key]

            if (market_symbol, resolution) not in time_frames:
                time_frames[(market_symbol, resolution)] = {field: [] for field in CandlePublisher.CACHE_FIELDS}

            for field in CandlePublisher.CACHE_FIELDS:
                time_frames[market_symbol, resolution][field].extend(slice_of_data[field])

        return time_frames

    @staticmethod
    def find_nearest_index(sorted_list: List[int], target: int):
        pos = bisect.bisect_left(sorted_list, target)
        if pos == 0 or pos == len(sorted_list):
            return pos

        before = pos - 1
        if abs(sorted_list[before] - target) <= abs(sorted_list[pos] - target):
            return before
        return pos

    def aggregate_result(
        self, time_series_data: Dict[Tuple[str, int], Dict[str, List]]
    ) -> Dict[str, Dict[str, List[Dict]]]:
        result: Dict[str, Dict[str, List[Dict]]] = {market.symbol: {} for market, _ in self.market_resolution_to_dts}
        for market_resolution_pair, dts in self.market_resolution_to_dts.items():
            market, primary_resolution = market_resolution_pair
            resolution_group = MarketCandle.get_resolution_key(primary_resolution)
            resolutions = CandlePublisher.RESOLUTION_GROUPS.get(resolution_group)
            for human_readable_resolution, factor in resolutions.items():
                for dt in dts:
                    start_of_candle = self.get_start_of_candle_by_factor(dt, primary_resolution, factor)

                    candle_data_block = time_series_data.get((market.symbol, primary_resolution))
                    if candle_data_block:
                        from_index = self.find_nearest_index(candle_data_block['time'], start_of_candle)

                        to_index = min(from_index + factor, len(candle_data_block['time']))

                        data = {
                            't': start_of_candle,
                            'o': candle_data_block['open'][from_index],
                            'h': max(candle_data_block['high'][from_index:to_index]),
                            'l': min(candle_data_block['low'][from_index:to_index]),
                            'c': candle_data_block['close'][to_index - 1],
                            'v': sum(candle_data_block['volume'][from_index:to_index]),
                        }
                        if human_readable_resolution not in result[market.symbol]:
                            result[market.symbol][human_readable_resolution] = []
                        serialized_data = self.normalize_result(data, market.symbol)
                        result[market.symbol][human_readable_resolution].append(serialized_data)
        return result

    @staticmethod
    def normalize_result(data: dict, symbol: str):
        """Apply precision and convert IRR to IRT"""
        is_rial = Market.by_symbol(symbol).dst_currency == Currencies.rls
        precision = -PRICE_PRECISIONS.get(symbol, Decimal('1e-2')).adjusted()
        for key in 'ohlc':
            data[key] = round(data[key], precision)
            if is_rial:
                data[key] /= 10
        data['v'] = round(data['v'], 8)
        return data

    @staticmethod
    def get_combined_cache_data(cache_key_map: Dict[str, Tuple[str, int]]) -> Dict[str, Dict]:
        if LongTermCandlesCache.cache() == ShortTermCandlesCache.cache():
            return dict(LongTermCandlesCache.cache().get_many(cache_key_map.keys()))

        long_cache_data = LongTermCandlesCache.cache().get_many([key for key in cache_key_map if key.endswith('short')])
        short_cache_data = ShortTermCandlesCache.cache().get_many(
            [key for key in cache_key_map if not key.endswith('short')]
        )
        return {**long_cache_data, **short_cache_data}

    def publish(self):
        cache_key_map = self.generate_cache_keys()

        cache_data = self.get_combined_cache_data(cache_key_map)
        time_series_data = self.extend_cache_slices(cache_key_map, cache_data)
        to_be_published_data = self.aggregate_result(time_series_data)
        candles_publisher(to_be_published_data)
