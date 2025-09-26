import functools
import json
from typing import Callable, Dict, List, Tuple
from uuid import UUID

import redis
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from redis.exceptions import RedisError

from exchange.accounts.ws import create_ws_authentication_param
from exchange.base.decorators import measure_function_execution
from exchange.base.logging import metric_incr, report_exception
from exchange.market.ws_serializers import serialize_order_for_user, serialize_rejected_order_for_user

_measure_publisher_execution = functools.partial(
    measure_function_execution,
    metric_prefix='publisher',
    metrics_flush_interval=30,
)


@functools.lru_cache(maxsize=1)
def _get_client() -> redis.Redis:
    return redis.Redis.from_url(settings.PUBLISHER_REDIS_URL)


def _check_publisher_activity(func: Callable):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RedisError as e:
            error_classname = e.__class__.__name__
            metric_incr('metric_websocket_publisher', labels=(error_classname,))
        except Exception:
            report_exception()

    return wrapper


def _get_public_channel_name(name) -> str:
    return f'public:{name}'


def _get_private_channel_name(name: str, user_uid: UUID) -> str:
    auth_param = create_ws_authentication_param(user_uid)
    return f'private:{name}#{auth_param}'


@_measure_publisher_execution(metric='Orderbook')
@_check_publisher_activity
def orderbook_publisher(market_symbol: str, update_time: int, last_trade_price: str, sell_book: list, buy_book: list):
    data = {'asks': sell_book, 'bids': buy_book, 'lastTradePrice': last_trade_price, 'lastUpdate': update_time}
    _get_client().publish(
        channel=_get_public_channel_name(f'orderbook-{market_symbol}'),
        message=json.dumps(data, separators=(',', ':')),
    )


@_measure_publisher_execution(metric='Trades')
@_check_publisher_activity
def trades_publisher(market_symbol: str, new_trade: dict):
    _get_client().publish(
        channel=_get_public_channel_name(f'trades-{market_symbol}'),
        message=json.dumps(new_trade, separators=(',', ':')),
    )


@_measure_publisher_execution(metric='MarketStats')
@_check_publisher_activity
def market_stats_publisher(market_symbol: str, market_stats: str):
    _get_client().publish(
        channel=_get_public_channel_name(f'market-stats-{market_symbol}'),
        message=market_stats,
    )


@_measure_publisher_execution(metric='MarketStatsAll')
@_check_publisher_activity
def all_market_stats_publisher(market_stats: str):
    _get_client().publish(
        channel=_get_public_channel_name(f'market-stats-all'),
        message=market_stats,
    )


@_measure_publisher_execution(metric='CandlePublisher')
@_check_publisher_activity
def candles_publisher(candles_data: Dict[str, Dict[str, List[Dict]]]):
    with _get_client().pipeline() as pipe:
        for market_symbol, resolutions in candles_data.items():
            for human_readable_resolution, data_list in resolutions.items():
                channel = f'candle-{market_symbol}-{human_readable_resolution}'
                for data in data_list:
                    pipe.publish(channel=_get_public_channel_name(channel), message=json.dumps(data))
        pipe.execute()


@_measure_publisher_execution(metric='PrivateTrades')
@_check_publisher_activity
def private_trade_publisher(new_trade: dict, user_uid: UUID):
    _get_client().publish(
        channel=_get_private_channel_name('trades', user_uid),
        message=json.dumps(new_trade, separators=(',', ':'), cls=DjangoJSONEncoder),
    )


@_measure_publisher_execution(metric='PrivateOrders')
@_check_publisher_activity
def private_order_publisher(order_data: List[Tuple[Dict, UUID]]):
    with _get_client().pipeline() as pipe:
        for data in order_data:
            pipe.publish(
                channel=_get_private_channel_name('orders', data[1]),
                message=json.dumps(data[0], separators=(',', ':')),
            )
        pipe.execute()


class OrderPublishManager:
    def __init__(self):
        self.orders_data: List[Tuple[Dict, UUID]] = []

    def add_order(self, order, last_trade, user_uid: UUID):

        if order.is_placed_by_system:
            return

        serialized_order = serialize_order_for_user(order, last_trade)
        self.orders_data.append((serialized_order, user_uid))

    def add_fail_message(self, data: Dict, user_uid: UUID):
        serialized_data = serialize_rejected_order_for_user(data)
        self.orders_data.append((serialized_data, user_uid))

    def publish(self):
        transaction.on_commit(functools.partial(private_order_publisher, order_data=self.orders_data))
        self.orders_data = []
