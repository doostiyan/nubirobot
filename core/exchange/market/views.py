"""Market Views"""
import datetime
import json
import random
from decimal import Decimal
from typing import List
from urllib.parse import parse_qs

from django.conf import settings
from django.core.cache import cache
from django.db import InternalError, transaction
from django.db.models import F, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django_ratelimit.decorators import Ratelimited, is_ratelimited, ratelimit
from model_utils import Choices
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST

from exchange.accounts.userlevels import UserLevelManager
from exchange.accounts.userprofile import UserProfileManager
from exchange.accounts.userstats import UserStatsManager
from exchange.base.api import (
    APIView,
    NobitexAPIError,
    ParseError,
    PublicAPIView,
    SemanticAPIError,
    api,
    is_request_from_unsupported_app,
    public_api,
    public_get_and_post_api,
    public_post_api,
    raise_on_email_not_verified,
)
from exchange.base.api_v2 import post_api
from exchange.base.decorators import measure_internal_bot_api_execution, measure_time, measure_time_cm
from exchange.base.helpers import download_csv, get_api_ratelimit, is_from_unsupported_app, paginate
from exchange.base.logging import report_event, report_exception
from exchange.base.models import (
    AVAILABLE_CRYPTO_CURRENCIES,
    AVAILABLE_MARKETS,
    RIAL,
    Currencies,
    Settings,
    get_currency_codename,
    get_market_symbol,
)
from exchange.base.money import money_is_zero
from exchange.base.parsers import (
    parse_bool,
    parse_choices,
    parse_client_order_id,
    parse_currency,
    parse_float,
    parse_int,
    parse_item_list,
    parse_money,
)
from exchange.base.publisher import OrderPublishManager
from exchange.base.serializers import serialize
from exchange.base.settings import NobitexSettings
from exchange.features.utils import is_feature_enabled
from exchange.market.coinmarketcap import VALID_MARKET_SYMBOLS
from exchange.market.decorators import capture_marketmaker_sentry_api_transaction
from exchange.market.depth_chart import MarketDepthChartGenerator
from exchange.market.exceptions import ParseMarketError
from exchange.market.marketmanager import MarketManager
from exchange.market.marketstats import MarketStats
from exchange.market.models import AutoTradingPermit, Market, MarketCandle, Order, OrderMatching, UserMarketsPreferences
from exchange.market.order_cancel import CANCEL_ORDER_BATCH_SIZE, cancel_batch_of_orders
from exchange.market.orderbook import OrderBookGenerator
from exchange.market.parsers import (
    parse_order_execution,
    parse_order_mode,
    parse_order_status,
    parse_order_trade_type,
    parse_order_type,
    parse_symbol,
)
from exchange.market.serializers import serialize_order


def create_cached_response(key, value, has_next=None):
    data = '{"status":"ok","' + key + '":' + value
    if has_next is not None:
        data += f',"hasNext":{"true" if has_next else "false"}'
    data += '}'
    return HttpResponse(
        data,
        content_type='application/json',
    )


def parse_order_parameters(request):
    # Check market
    src_currency = parse_currency(request.g('srcCurrency'), required=True)
    dst_currency = parse_currency(request.g('dstCurrency'), required=True)
    market = Market.get_for(src_currency, dst_currency)
    if not market:
        return None, {
            'status': 'failed',
            'message': 'Market Validation Failed',
            'code': 'InvalidMarketPair',
        }
    if not market.is_active:
        return None, {
            'status': 'failed',
            'message': 'Market Validation Failed',
            'code': 'MarketClosed',
        }

    order = Order(
        order_type=parse_order_type(request.g('type'), required=True),
        execution_type=parse_order_execution(request.g('execution')),
        src_currency=src_currency,
        dst_currency=dst_currency,
        amount=parse_money(request.g('amount'), required=True),
        price=parse_money(request.g('price')),
    )
    order.market = market
    return order, None


class OrderCreateMixin:
    trade_type = Order.TRADE_TYPES.spot
    restrictions = ('Trading',)

    def clean_order(self, order_data: dict, is_pro: bool) -> list:
        user = self.request.user
        initials = self.get_initials()
        is_oco = parse_order_mode(order_data.get('mode')) == 'oco'
        order_type = initials.get('order_type') or parse_order_type(order_data.get('type'), required=True)
        execution_type = parse_order_execution(order_data.get('execution'))
        src_currency = initials.get('src_currency') or parse_currency(order_data.get('srcCurrency'), required=True)
        dst_currency = initials.get('dst_currency') or parse_currency(order_data.get('dstCurrency'), required=True)
        amount = parse_money(order_data.get('amount'), required=True, field=Order.amount)
        price = parse_money(order_data.get('price'), field=Order.price)
        client_order_id = parse_client_order_id(order_data.get('clientOrderId'), required=False)
        param1 = None
        aux_price = None

        # Get parameters for stop orders
        if execution_type in Order.STOP_EXECUTION_TYPES or is_oco:
            param1 = parse_money(order_data.get('stopPrice'), required=True, field=Order.param1)

        if is_oco:
            aux_price = parse_money(order_data.get('stopLimitPrice'), required=True, field=Order.price)

        # Check Price
        if not price or money_is_zero(price):
            if execution_type in Order.MARKET_EXECUTION_TYPES:
                price = Decimal('0')
            else:
                raise NobitexAPIError('InvalidOrderPrice', 'Price Validation Failed')
        if is_oco and (not aux_price or money_is_zero(aux_price)):
            raise NobitexAPIError('InvalidOrderPrice', 'Price Validation Failed')

        # Check market
        market = Market.get_for(src_currency, dst_currency)
        if not market:
            raise NobitexAPIError('InvalidMarketPair', 'Market Validation Failed')
        if not market.is_active:
            raise NobitexAPIError('MarketClosed', 'Market Validation Failed')

        # Timed Launch
        if market.is_alpha and not is_feature_enabled(user, 'new_coins'):
            raise NobitexAPIError('MarketClosed', 'Market is not opened yet!')

        # Preparing order
        order_fields = {
            'src_currency': src_currency,
            'dst_currency': dst_currency,
            'user': user,
            'order_type': order_type,
            'amount': amount,
            'price': price,
            'client_order_id': client_order_id,
        }
        if is_oco:
            orders_fields = [
                {
                    **order_fields,
                    'execution_type': Order.EXECUTION_TYPES.limit,
                },
                {
                    **order_fields,
                    'execution_type': Order.EXECUTION_TYPES.stop_limit,
                    'price': aux_price,
                    'param1': param1,
                    'client_order_id': None,
                }
            ]
        else:
            orders_fields = [
                {
                    **order_fields,
                    'execution_type': execution_type,
                    'param1': param1,
                }
            ]

        # Check for duplicate order requests
        if not is_pro:
            if self.is_duplicate(orders_fields):
                raise NobitexAPIError('DuplicateOrder', 'Duplicate orders are ignored for 10 seconds')

        return orders_fields

    @staticmethod
    def get_initials() -> dict:
        return {}

    @classmethod
    def is_duplicate(cls, orders_fields: list) -> bool:
        similar_fields = {**orders_fields[0], 'pair__isnull': len(orders_fields) == 1}
        for field in ('execution_type', 'price'):
            if field in similar_fields and not similar_fields[field]:
                similar_fields.pop(field)
        check_period = now() - datetime.timedelta(seconds=10)
        similar_previous_trades = Order.objects.filter(
            trade_type=cls.trade_type, created_at__gte=check_period, **similar_fields
        )
        return similar_previous_trades.exists()

    def is_closed_market(self, order_data):
        src_currency = order_data.get('src_currency')
        dst_currency = order_data.get('dst_currency')

        base_rate_limit = self.get_base_rate_limit()
        market_symbol = get_market_symbol(src_currency, dst_currency)
        return is_ratelimited(
            request=self.request,
            key='user_or_ip',
            rate=get_api_ratelimit(base_rate_limit, default_none=True),
            group=f'exchange.market.views.OrderCreate.create_orders.{market_symbol}',
            increment=True,
        )

    @staticmethod
    def get_base_rate_limit():
        return '300/10m'

    def create_orders(self, orders_fields: list, channel: int) -> dict:
        base_rate_limit = self.get_base_rate_limit()

        if self.is_closed_market(orders_fields[0]):
            raise NobitexAPIError(
                message='MarketTemporaryClosed',
                description='به دلیل افزایش حجم معاملات در این بازار، لطفاً دقایقی صبر کنید و مجدداً تلاش فرمایید.',
            )

        if is_ratelimited(
            request=self.request,
            key='user_or_ip',
            rate=get_api_ratelimit(base_rate_limit),
            group='exchange.market.views.OrderCreate.create_orders',
            increment=True,
        ):
            raise Ratelimited()

        order = None
        orders = []
        with transaction.atomic():
            for order_fields in orders_fields:
                order = self._create_order(**order_fields, pair=order, channel=channel)
                orders.append(order)
        if len(orders) == 1:
            return {'order': order}
        return {'orders': orders}

    @staticmethod
    def _create_order(**kwargs) -> Order:
        order: Order
        order, err = MarketManager.create_order(**kwargs)
        if err is not None:
            if err == 'LargeOrder':
                dst_currency = market.dst_currency if (market := kwargs.get('market')) else kwargs.get('dst_currency')
                max_total_price = settings.NOBITEX_OPTIONS['maxOrders']['spot'][dst_currency]

                raise NobitexAPIError(err, f'Order value is limited to below {max_total_price:,}.')
            if err == 'MarketExecutionTypeTemporaryClosed':
                msg = (
                    'در حال حاضر امکان ثبت سفارش سریع در این بازار وجود ندارد.'
                    ' لطفاً از سفارش گذاری با تعیین قیمت استفاده نمایید.'
                )
                raise NobitexAPIError(err, msg)
            raise NobitexAPIError(err, 'Order Validation Failed')
        return order

    def check_user(self):
        if self.request.user.is_restricted(*self.restrictions):
            raise NobitexAPIError('TradingUnavailable')
        if self.trade_type == Order.TRADE_TYPES.margin:
            raise_on_email_not_verified(self.request.user)
        if not UserLevelManager.is_eligible_to_trade(self.request.user):
            raise NobitexAPIError('TradeLimitation')

    def get_channel(self):
        """Source Client Detection"""
        if self.g('client') == 'web_v1':
            return Order.CHANNEL.web_v1
        if self.g('client') == 'web_v2':
            return Order.CHANNEL.web_v2
        ua = self.request.headers.get('user-agent') or 'unknown'
        return MarketManager.detect_order_channel(ua)

    def build_order_response(self, order_data, channel, is_pro, order_publish_manager, user):
        try:
            orders_fields = self.clean_order(order_data, is_pro)
            data = self.create_orders(orders_fields, channel)
            response = {'status': 'ok', **data}
        except NobitexAPIError as e:
            response = {
                'status': 'failed',
                'code': e.code,
                'message': e.description or e.code,
                'clientOrderId': order_data.get('clientOrderId'),
            }
        except ParseError as e:
            response = {
                'status': 'failed',
                'code': 'ParseError',
                'message': str(e),
                'clientOrderId': order_data.get('clientOrderId'),
            }

        if 'orders' in response:
            for order in response['orders']:
                order_publish_manager.add_order(order, None, user.uid)
        elif 'order' in response:
            order = response['order']
            order_publish_manager.add_order(order, None, user.uid)
        elif order_data.get('clientOrderId'):
            order_publish_manager.add_fail_message(response, user.uid)

        return response


class OrderCreateView(OrderCreateMixin, APIView):
    serialize_level = 2

    @method_decorator(ratelimit(key='user_or_ip', rate=get_api_ratelimit('300/10m'), block=True))
    @method_decorator(measure_internal_bot_api_execution(api_label='marketInBotOrderCreate'))
    @method_decorator(capture_marketmaker_sentry_api_transaction)
    def post(self, request, **_):
        """ API for placing an order

            POST /market/orders/add

            Note: Binance ordering rate limit is 100/10s and 200K/day
        """
        is_pro = parse_bool(self.g('pro'))
        channel = self.get_channel()

        # Check app version
        if is_request_from_unsupported_app(request):
            raise SemanticAPIError('PleaseUpdateApp', 'Please Update App')

        self.check_user()

        # Warm up user level cache for faster MatchFees step in matcher
        UserStatsManager.get_user_vip_level(self.request.user.id)

        keys = (
            'mode', 'type', 'execution', 'srcCurrency', 'dstCurrency', 'amount', 'price', 'stopPrice',
            'stopLimitPrice', 'clientOrderId'
        )

        order_data = {key: self.g(key) for key in keys}

        order_publish_manager = OrderPublishManager()

        response = self.build_order_response(order_data, channel, is_pro, order_publish_manager, request.user)

        order_publish_manager.publish()

        if response['status'] != 'ok':
            if response['code'] == 'ParseError':
                return Response(response, status=HTTP_400_BAD_REQUEST)
            return self.response(response)

        return self.response(response, {'level': self.serialize_level})



class OrderBatchCreateView(OrderCreateMixin, APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate=get_api_ratelimit('300/10m'), block=True))
    @method_decorator(measure_internal_bot_api_execution(api_label='marketInBotOrderBatchCreate'))
    @method_decorator(capture_marketmaker_sentry_api_transaction)
    def post(self, request, **_):
        """ API for placing an order

            POST /market/orders/batch-add
        """
        is_pro = parse_bool(self.g('pro'))
        channel = self.get_channel()

        self.check_user()

        data = parse_item_list(self.g('data'), item_type=dict, required=True)
        responses = []
        order_publish_manager = OrderPublishManager()
        for order_data in data:
            try:
                response = self.build_order_response(order_data, channel, is_pro, order_publish_manager, request.user)
            except Ratelimited:
                break
            except Exception as e:
                report_exception()
                response = {
                    'status': 'failed',
                    'code': 'Unknown',
                    'message': e,
                    'clientOrderId': order_data.get('clientOrderId'),
                }
            responses.append(response)

        order_publish_manager.publish()
        return self.response({'status': 'ok', 'results': responses}, {'level': 2})


@ratelimit(key='user_or_ip', rate='60/1m', block=True)
@api
def orders_estimate(request):
    user = request.user
    order, err = parse_order_parameters(request)
    if err:
        return err
    if not order.price or not order.amount:
        return {
            'status': 'failed',
            'message': 'Order Validation Failed',
        }
    fee = MarketManager.get_trade_fee(
        order.market,
        user=user,
        is_maker=False,
        amount=order.amount if order.is_buy else order.total_price,
    )
    return {
        'status': 'ok',
        'order': {
            'fee': fee,
        },
    }


@ratelimit(key='user_or_ip', rate=get_api_ratelimit('300/1m'), block=True)
@api
def orders_status(request):
    # Parse Inputs
    order_id = parse_int(request.g('id'), minimum=1, required=False)
    level = parse_int(request.g('level', 2), required=False)
    client_order_id = parse_client_order_id(request.g('clientOrderId'), required=False)

    if order_id is None and client_order_id is None:
        return {
            'status': 'failed',
            'code': 'NullIdAndClientOrderId',
            'message': 'Both id and clientOrderId cannot be null',
        }

    user = request.user

    if order_id:
        order = get_object_or_404(Order, user=user, pk=order_id)
    else:
        order = get_object_or_404(
            Order,
            user=user,
            client_order_id=client_order_id,
            status__in=Order.OPEN_STATUSES,
        )

    response = {
        'status': 'ok',
        'order': serialize_order(order, {'level': level, 'user': user}),
    }

    if level >= 3:
        filter_query = Q(sell_order_id=order.id) if order.is_sell else Q(buy_order_id=order.id)
        order_matchings = OrderMatching.objects.filter(filter_query).select_related('market')
        response.update(
            {
                'trades': serialize(
                    order_matchings,
                    opts={
                        'user': user,
                        'market': False,
                        'get_id': True,
                        'trade_type': 'buy' if order.is_buy else 'sell',
                    },
                    ignore_keys=['srcCurrency', 'dstCurrency', 'market', 'type'],
                ),
            },
        )
    return response


@ratelimit(key='user_or_ip', rate=get_api_ratelimit('30/1m'), block=True)
@measure_internal_bot_api_execution(api_label='marketInBotOrdersList')
@api
def orders_list(request):
    """ POST /market/orders/list

        This API sets no_order cache flag for users with no order
    """
    OrdersListOrder = Choices(
        (('id', 'created_at'), 'id', 'id asc'),
        (('-id', '-created_at'), '-id', 'id desc'),
        (('created_at',), 'created_at', 'created_at asc'),
        (('-created_at',), '-created_at', 'created_at desc'),
        (('price',), 'price', 'price asc'),
        (('-price',), '-price', 'price desc'),
    )
    order = request.g('order')
    order_type = parse_order_type(request.g('type'))
    execution = parse_order_execution(request.g('execution'))
    trade_type = parse_order_trade_type(request.g('tradeType'))
    src_currency = parse_currency(request.g('srcCurrency'))
    dst_currency = parse_currency(request.g('dstCurrency'))
    details = parse_int(request.g('details', 1))
    from_id = parse_int(request.g('fromId'))

    # Param: status
    status = request.g('status')
    if not status:
        status = 'open'
    if status == 'active':
        # Until front is updated to request open orders, we also accept "active" to mean "open"
        status = 'open'
    if status not in ['all', 'open', 'done', 'close', 'undone']:
        # Deprecating other/invalid status choices gradually
        status = 'open'
    if status == 'close' and is_from_unsupported_app(request, 'bigint_order_id'):
        raise SemanticAPIError('PleaseUpdateApp', 'Please Update App')

    # Deprecated parameters
    my_orders_only = request.g('myOrdersOnly', 'yes') == 'yes'
    qs = request.GET.urlencode()
    download = parse_qs(qs).get('download', ['false'])[0] == 'true'

    # Load check
    if settings.LOAD_LEVEL >= 5 and download:
        return HttpResponse(status=429)
    if not my_orders_only:
        return {'status': 'ok', 'orders': []}

    # Check if request can be served from cache
    user = request.user

    # Filter Objects
    has_all_user_active_orders = status in ['all', 'open']
    orders = Order.objects.filter(user=user)
    if order_type:
        orders = orders.filter(order_type=order_type)
        has_all_user_active_orders = False
    if src_currency:
        orders = orders.filter(src_currency=src_currency)
        has_all_user_active_orders = False
    if dst_currency:
        orders = orders.filter(dst_currency=dst_currency)
        has_all_user_active_orders = False
    if execution:
        orders = orders.filter(execution_type=execution)
        has_all_user_active_orders = False
    if trade_type:
        orders = orders.filter(trade_type=trade_type)
        has_all_user_active_orders = False
    if from_id:
        orders = orders.filter(pk__gte=from_id)
        has_all_user_active_orders = False

    # Filter by Status
    if status == 'all':
        pass
    elif status == 'done':
        done_statuses = [Order.STATUS.done, Order.STATUS.active, Order.STATUS.canceled]
        orders = orders.filter(status__in=done_statuses, matched_amount__gt=0)
    elif status == 'undone':
        orders = orders.filter(Q(status=Order.STATUS.active) | Q(status=Order.STATUS.canceled, matched_amount__gt=0))
    elif status == 'open':
        orders = orders.filter(status__in=Order.OPEN_STATUSES)
    elif status == 'close':
        orders = orders.filter(status__in=[Order.STATUS.done, Order.STATUS.canceled])
    else:
        report_event('AssertionError', extras={'status': status})

    # Ordering
    order_by = parse_choices(OrdersListOrder, order, required=False)
    if not order_by:
        if from_id:
            order_by = getattr(OrdersListOrder, '-id')
        elif not order_type:
            order_by = getattr(OrdersListOrder, '-created_at')
        elif order_type == Order.ORDER_TYPES.buy:
            order_by = getattr(OrdersListOrder, '-price')
        elif order_type == Order.ORDER_TYPES.sell:
            order_by = OrdersListOrder.price

    if from_id and 'id' not in order_by and '-id' not in order_by:
        order_by = (*order_by, *getattr(OrdersListOrder, '-id'))

    orders = orders.order_by(*order_by)

    if trade_type != Order.TRADE_TYPES.spot:
        orders = orders.annotate(leverage=F('position__leverage'), side=F('position__side'))

    # Pagination
    if not download:
        with measure_time_cm(metric=f'order_list_query_milliseconds__{trade_type or 0}'):
            max_page = 1 if from_id else None
            max_page_size = 1000 if from_id else None
            orders, has_next = paginate(
                orders,
                page_size=100,
                request=request,
                check_next=True,
                max_page=max_page,
                max_page_size=max_page_size,
            )
    else:
        orders = orders[:1000]
        has_next = None

    # Serialize orders
    opts = {'level': 2 if (details > 1 or download) else 1, 'user': user}
    serialized_orders = []
    for order in orders:
        if order.channel == Order.CHANNEL.system_block:
            has_all_user_active_orders = False
            continue
        serialized_orders.append(serialize_order(order, opts=opts))

    # Mark users with no order
    if not serialized_orders and has_all_user_active_orders:
        cache.set('user_{}_no_order'.format(user.id), True, 900)

    # CSV Download Mode
    if download:
        headers = ['id', 'created_at', 'type', 'srcCurrency', 'dstCurrency', 'price', 'amount', 'totalPrice', 'fee',
                   'matchedAmount', 'status']
        return download_csv('orders-history', serialized_orders, headers)

    # Serialize, cache if possible, and return response
    orders_result = json.dumps(serialize(serialized_orders))
    return create_cached_response('orders', orders_result, has_next=has_next)


@ratelimit(key='user_or_ip', rate='6/m', block=True)
@public_post_api
def v2_orderbook(request):
    """Deprecated API, use GET /v2/orderbook/SYMBOL instead."""
    symbol = parse_symbol(request.g('symbol'))
    # Get orderbook from cache
    orderbook_bids = cache.get('orderbook_{}_bids'.format(symbol))
    orderbook_asks = cache.get('orderbook_{}_asks'.format(symbol))
    # Recreate orderbook if not cached (daemon is not running)
    if not orderbook_bids or not orderbook_asks:
        report_event('Orderbook does not have any cache')
        OrderBookGenerator.create_market_orderbooks(symbol)
        orderbook_bids = cache.get(f'orderbook_{symbol}_bids')
        orderbook_asks = cache.get(f'orderbook_{symbol}_asks')
    # Construct and return response
    response = '{"status":"ok","bids":' + orderbook_bids + ',"asks":' + orderbook_asks + '}'
    return HttpResponse(response, content_type='application/json')


@method_decorator(ratelimit(key='user_or_ip', rate='300/1m', block=True), name='get')
class OrderBookV2(PublicAPIView):
    """ GET /v2/orderbook/SYMBOL """

    def get(self, request, symbol):
        if symbol == 'all':
            orderbook = {}
            available_markets = Market.objects.all().values_list('src_currency', 'dst_currency')
            for (src, dst) in available_markets:
                market_symbol = get_market_symbol(src, dst)
                orderbook[market_symbol] = self.construct_orderbook_entry(market_symbol)
            orderbook = json.dumps(orderbook, separators=(',', ':'))
            response = '{"status":"ok"' + (',' if len(orderbook) > 2 else '') + orderbook[1:]
        else:
            symbol = parse_symbol(symbol)
            response = json.dumps(self.construct_single_symbol_orderbook(symbol))
        return HttpResponse(response, content_type='application/json')

    def construct_single_symbol_orderbook(self, symbol):
        return {
            "status": "ok",
            "lastUpdate": json.loads(self.get_last_update_time(symbol)),
            "lastTradePrice": self.get_last_trade_price(symbol),
            "bids": json.loads(self.get_bids(symbol)),
            "asks": json.loads(self.get_asks(symbol)),
        }

    def construct_orderbook_entry(self, market_symbol):
        last_trade_prices = self.get_all_last_trade_prices()
        bids = self.get_all_bids()
        asks = self.get_all_asks()
        update_times = self.get_all_update_times()

        return {
            'lastUpdate': int(update_times.get(f'orderbook_{market_symbol}_update_time'))
            if update_times.get(f'orderbook_{market_symbol}_update_time')
            else None,
            'lastTradePrice': last_trade_prices.get(f'orderbook_{market_symbol}_last_trade_price', ''),
            'bids': json.loads(bids.get(f'orderbook_{market_symbol}_bids', '[]')),
            'asks': json.loads(asks.get(f'orderbook_{market_symbol}_asks', '[]')),
        }

    def get_bids(self, symbol) -> str:
        return self._get_orderbook_items(symbol, 'bid')

    def get_asks(self, symbol) -> str:
        return self._get_orderbook_items(symbol, 'ask')

    @staticmethod
    def _get_orderbook_items(symbol, tp) -> str:
        orderbook_items = cache.get(f'orderbook_{symbol}_{tp}s')
        if not orderbook_items:  # Recreate orderbook if not cached (daemon is not running)
            report_event(f'Orderbook does not have any {tp} cache')
            OrderBookGenerator.create_market_orderbooks(Market.by_symbol(symbol))
            orderbook_items = cache.get(f'orderbook_{symbol}_{tp}s') or '[]'
        return orderbook_items

    @staticmethod
    def get_last_update_time(symbol):
        return cache.get(f'orderbook_{symbol}_update_time') or 'null'

    @staticmethod
    def get_last_trade_price(symbol):
        return cache.get(f'orderbook_{symbol}_last_trade_price') or ''

    @staticmethod
    def get_all_bids():
        bids_keys = [f'orderbook_{symbol}_bids' for symbol in VALID_MARKET_SYMBOLS]
        return cache.get_many(bids_keys)

    @staticmethod
    def get_all_asks():
        asks_keys = [f'orderbook_{symbol}_asks' for symbol in VALID_MARKET_SYMBOLS]
        return cache.get_many(asks_keys)

    @staticmethod
    def get_all_update_times():
        update_time_keys = [f'orderbook_{symbol}_update_time' for symbol in VALID_MARKET_SYMBOLS]
        return cache.get_many(update_time_keys)

    @staticmethod
    def get_all_last_trade_prices():
        trade_price_keys = [f'orderbook_{symbol}_last_trade_price' for symbol in VALID_MARKET_SYMBOLS]
        return cache.get_many(trade_price_keys)


@method_decorator(ratelimit(key='user_or_ip', rate='300/1m', block=True), name='get')
class OrderBookV3(OrderBookV2):
    """GET /v3/orderbook/SYMBOL

    Swapped the previous mistakenly misplaced `bids` and `asks` for the sake of global convention
    """

    def construct_single_symbol_orderbook(self, symbol):
        response = super().construct_single_symbol_orderbook(symbol)

        # Since, `asks` should correspond sell orders and `bids` should correspond buy orders
        # we should swap `bids` and `asks`:
        response['bids'], response['asks'] = response['asks'], response['bids']

        return response

    def construct_orderbook_entry(self, market_symbol):
        response = super().construct_orderbook_entry(market_symbol)

        # Since, `asks` should correspond sell orders and `bids` should correspond buy orders
        # we should swap `bids` and `asks`:
        response['bids'], response['asks'] = response['asks'], response['bids']

        return response


@ratelimit(key='user_or_ip', rate=get_api_ratelimit('90/1m'), block=True)
@api
@capture_marketmaker_sentry_api_transaction
def orders_update_status(request):
    """ POST /market/orders/update-status
    """
    # Parse Inputs
    status = parse_order_status(request.g('status'), required=True)
    order_id = parse_int(request.g('order'), minimum=1, required=False)
    client_order_id = parse_client_order_id(request.g('clientOrderId'), required=False)

    if order_id is None and client_order_id is None:
        return {
            'status': 'failed',
            'code': 'NullIdAndClientOrderId',
            'message': 'Both id and clientOrderId cannot be null',
        }

    user = request.user

    if order_id:
        order = get_object_or_404(Order, user=user, pk=order_id)
    else:
        order = get_object_or_404(
            Order,
            user=user,
            client_order_id=client_order_id,
            status__in=Order.OPEN_STATUSES,
        )

    # To prevent deadlock with matcher, we prefer OCO orders to start canceling
    # from the active limit order if exists. So inactive stop order is switched
    if order.status == Order.STATUS.inactive and order.pair and not order.pair.matched_amount:
        order, order.pair = order.pair, order

    # Update Order Status
    ok = order.update_status(status, manual=True)

    # Reload order parameters from database
    order.refresh_from_db()

    return {
        'status': 'ok' if ok else 'failed',
        'updatedStatus': order.get_status_display(),
        # serialize latest version of the order detailed.
        'order': serialize_order(order, {'level': 2, 'user': user}),
    }


@ratelimit(key='user_or_ip', rate=get_api_ratelimit('30/1m'), block=True)
@measure_internal_bot_api_execution(api_label='marketInBotOrdersCancelOld')
@api
def orders_cancel_old(request):
    user = request.user
    src_currency = parse_currency(request.g('srcCurrency'))
    dst_currency = parse_currency(request.g('dstCurrency'))
    hours = parse_float(request.g('hours'))
    execution_type = parse_order_execution(request.g('execution'))
    trade_type = parse_order_trade_type(request.g('tradeType'))

    # Filter requested orders
    orders = Order.objects.filter(user=user, status=Order.STATUS.active).order_by(
        'created_at'
    )  # Same order as matcher lock
    if src_currency:
        orders = orders.filter(src_currency=src_currency)
    if dst_currency:
        orders = orders.filter(dst_currency=dst_currency)
    if hours:
        orders = orders.filter(created_at__lt=now() - datetime.timedelta(minutes=round(hours * 60)))
    if execution_type:
        orders = orders.filter(execution_type=execution_type)
    if trade_type:
        orders = orders.filter(trade_type=trade_type)

    cancel_batch_of_orders(user_id=user.id, order_ids=orders.values_list('id', flat=True))
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate=get_api_ratelimit('10/1m'), block=True)
@measure_internal_bot_api_execution(api_label='marketInBotOrdersCancelBatch')
@post_api
@measure_time(metric='orders_cancel_batch', verbose=False)
@capture_marketmaker_sentry_api_transaction
def orders_cancel_batch(request):
    """
       Cancel a batch of orders (batch size = 20)
        return:
        {
            'status': 'ok',
            'orders': {
                '1':{
                    'status': 'failed',
                    'message': 'Systematically placed orders are immutable'
                    },
                '2':{
                    'status': 'ok',
                    'message': ''
                }
            }
        }
    """
    user = request.user

    # check data-form and json
    order_ids_data = []
    try:
        body_unicode = request.body.decode('utf-8')
        body_data = json.loads(body_unicode)
        if 'orderIds' in body_data:
            order_ids_data = body_data['orderIds']
    except json.decoder.JSONDecodeError:
        order_ids_data = request.POST.getlist('orderIds')

    if not order_ids_data:
        return {
            'status': 'failed',
            'code': 'orderIdsListIsEmpty',
            'message': 'Order_ids list is empty',
        }
    # check batch size
    if len(order_ids_data) > CANCEL_ORDER_BATCH_SIZE:
        return {
            'status': 'failed',
            'code': 'batchSize',
            'message': 'The maximum number of orderIds should be 20.',
        }

    # parse ids
    order_ids = {parse_int(o_id, minimum=1, required=True) for o_id in order_ids_data}

    orders, filtered_order_ids = cancel_batch_of_orders(user_id=user.id, order_ids=order_ids)
    response = {
        'status': 'ok',
        'message': '',
        'orders': {},
    }

    order_results = {}
    for order in orders:
        if order.id in order_ids:
            if order.status == Order.STATUS.canceled:
                if order.id in filtered_order_ids:
                    order_results[str(order.id)] = {
                        'status': 'ok',
                    }
                else:
                    order_results[str(order.id)] = {
                        'status': 'failed',
                        'message': 'The order is already canceled.',
                    }
            elif order.status == Order.STATUS.done:
                order_results[str(order.id)] = {
                    'status': 'failed',
                    'message': 'The order is already completed.',
                }
            else:
                if order.is_placed_by_system:
                    order_results[str(order.id)] = {
                        'status': 'failed',
                        'message': 'Systematically placed orders are immutable.',
                    }
                else:
                    order_results[str(order.id)] = {
                        'status': 'failed',
                        'message': 'This order cannot be canceled.',
                    }
            order_ids.remove(order.id)

    for order_id in order_ids:
        order_results[str(order_id)] = {
            'status': 'failed',
            'message': 'The order id not found',
        }
    response['orders'] = order_results
    return response


@ratelimit(key='user_or_ip', rate='20/1m', block=True)
@public_get_and_post_api
def market_stats(request):
    sources_query_params = request.g('srcCurrency')
    destinations_query_params = request.g('dstCurrency')

    sources = [get_currency_codename(c) for c in AVAILABLE_CRYPTO_CURRENCIES]
    destinations = ['rls', 'usdt']

    sources = sources_query_params.split(',') if sources_query_params else sources
    destinations = destinations_query_params.split(',') if destinations_query_params else destinations

    market_stat_keys: List[str] = []
    for source in sources:
        src_currency = parse_currency(source)
        for destination in destinations:
            if source == destination:
                continue
            dst_currency = parse_currency(destination)
            market_stat_keys.append(f'market_stats_{src_currency}-{dst_currency}')

    stats = ''
    cached_markets_stats = cache.get_many(market_stat_keys)
    currency_mapping = {v: k for k, v in Currencies._identifier_map.items()}

    for market_stat_key in market_stat_keys:
        currency_pair: str = market_stat_key.split('_')[-1]
        src_currency, dst_currency = currency_pair.split('-')
        if [int(src_currency), int(dst_currency)] not in AVAILABLE_MARKETS:
            market_stat = '{"isClosed":true,"isClosedReason":"InvalidMarketPair"}'
        elif market_stat_key not in cached_markets_stats:
            market = Market.get_for(src_currency, dst_currency)
            if market:
                market_stat = MarketStats.calculate_market_stats(market)
            else:
                market_stat = '{"isClosed":true,"isClosedReason":"InvalidMarketPair"}'
        else:
            market_stat = cached_markets_stats[market_stat_key]
        if stats:
            stats += ','
        stats += f'"{currency_mapping[int(src_currency)]}-{currency_mapping[int(dst_currency)]}":{market_stat}'

    # Global Binance Statistics
    stats_binance = cache.get('market_stats_binance')
    if not stats_binance:
        stats_binance = MarketStats.calculate_market_stats_binance()

    response = '{"status":"ok","stats":{' + stats + '},"global":{"binance":' + stats_binance + '}}'
    return HttpResponse(response, content_type='application/json')


@ratelimit(key='user_or_ip', rate='100/10m', block=True)
@public_post_api
def market_global_stats(request):
    cache_key = 'market_global_stats'
    stats = cache.get(cache_key)
    if not stats:
        stats = {
            'status': 'ok',
            'markets': {
                'binance': cache.get('binance_prices') or {},
            },
        }
        stats = json.dumps(stats)
        cache.set(cache_key, stats, 60)
    return HttpResponse(stats, content_type='application/json')


@ratelimit(key='user_or_ip', rate='60/1m', method='POST', block=True)
@public_post_api
def usd_value(request):
    system_usd = json.loads(Settings.get('usd_value'))
    return {
        'status': 'ok',
        'usdValue': system_usd
    }


@api
def autotrade_get_options(request):
    user = request.user
    try:
        atp = AutoTradingPermit.objects.get(user=user)
    except AutoTradingPermit.DoesNotExist:
        return {
            'status': 'ok',
            'enabled': False,
        }
    return {
        'status': 'ok',
        'enabled': True,
        'options': atp.get_options(),
        'values': atp.get_values(),
    }


@api
def autotrade_set_options(request):
    user = request.user
    options = request.g('options')
    options = json.loads(options or '{}')
    atp = AutoTradingPermit.objects.get_or_create(user=user)[0]
    atp.update_options(options)
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate=get_api_ratelimit('30/1m'), block=True)
@measure_internal_bot_api_execution(api_label='marketInBotTradesList')
@api
def trades_list(request):
    """ POST /market/trades/list
    """
    user = request.user
    src_currency = parse_currency(request.g('srcCurrency'))
    dst_currency = parse_currency(request.g('dstCurrency'))
    if src_currency or dst_currency:
        market = Market.get_for(src_currency, dst_currency)
        if not market:
            return None, {
                'status': 'failed',
                'message': 'Market Validation Failed',
                'code': 'InvalidMarketPair',
            }
    else:
        market = None
    from_id = parse_int(request.g('fromId'))
    days_to_show = 3
    trades = OrderMatching.get_trades(
        market=market,
        date_from=now() - datetime.timedelta(days=days_to_show),
    ).filter(Q(seller=user) | Q(buyer=user))
    if from_id:
        trades = trades.filter(id__gte=from_id)

    trade_type = request.g('tradeType')
    if trade_type == 'sell':
        trades = trades.filter(seller=user)
    elif trade_type == 'buy':
        trades = trades.filter(buyer=user)
    elif trade_type is not None and trade_type != '':
        raise ParseError('Invalid trade type. Acceptable types include: buy, sell')

    trades = trades.select_related('market').only(
        'market__src_currency',
        'market__dst_currency',
        'seller_id',
        'sell_order_id',
        'buy_order_id',
        'created_at',
        'matched_price',
        'matched_amount',
        'sell_fee_amount',
        'buy_fee_amount',
    )

    # Result Ordering
    # Note: To prevent DB planner from preferring "Parallel Index Scan Backward using created_at"
    # over "BitmapOr(buyer_id, seller_id)", we also add id to end of ORDER BY clause.
    trade_order = request.g('tradeOrder')
    if trade_order == 'asc':
        trades = trades.order_by('created_at', 'id')
    else:
        trades = trades.order_by('-created_at', '-id')

    # CSV Download: Disabled in usual load level of 8
    download = parse_bool(request.GET.get('download'))
    if settings.LOAD_LEVEL >= 5 and download:
        return HttpResponse(status=429)
    if download:
        trades = trades[:1000]
        trades = serialize(
            trades,
            opts={
                'user': user,
                'market': False,
                'get_id': True,
                'get_order_id': True,
            },
        )
        headers = [
            'id',
            'orderId',
            'srcCurrency',
            'dstCurrency',
            'timestamp',
            'market',
            'price',
            'amount',
            'total',
            'type',
            'fee',
        ]
        return download_csv('trades-history', trades, headers)

    # Paginate and return result
    trades, has_next = paginate(trades, page_size=30, request=request, check_next=True, max_page=100, max_page_size=500)
    return {
        'status': 'ok',
        'trades': serialize(trades, opts={
            'user': user,
            'market': False,
            'get_id': True,
            'get_order_id': True,
            'trade_type': trade_type
        }),
        'hasNext': has_next,
    }


@ratelimit(key='user_or_ip', rate='3/m', block=True)
@public_post_api
def v2_trades(request):
    """Deprecated API, use GET /v2/trades/SYMBOL instead."""
    symbol = parse_symbol(request.g('symbol'))
    # Get recent trades from cache
    recent_trades = cache.get('trades_{}'.format(symbol))
    if recent_trades is None:
        recent_trades = MarketManager.update_recent_trades_cache(symbol)
    # Construct and return response
    response = '{"status":"ok","trades":' + recent_trades + '}'
    return HttpResponse(response, content_type='application/json')


@ratelimit(key='user_or_ip', rate='60/1m', block=True)
@public_api
def v2_trades_get(request, symbol):
    """ GET /v2/trades/SYMBOL """
    # Get recent trades from cache
    symbol = parse_symbol(symbol)
    recent_trades = cache.get('trades_{}'.format(symbol))
    if recent_trades is None:
        recent_trades = MarketManager.update_recent_trades_cache(symbol)
    # Construct and return response
    response = '{"status":"ok","trades":' + recent_trades + '}'
    return HttpResponse(response, content_type='application/json')


@ratelimit(key='user_or_ip', rate='20/1m', block=True)
@public_get_and_post_api
def v2_crypto_prices(request):
    """ POST /v2/crypto-prices """
    response_cache_key = 'response_v2_crypto_prices'
    response = cache.get(response_cache_key)
    if not response:
        binance_prices = cache.get('binance_prices') or {}
        prices = {}
        resolution = MarketCandle.RESOLUTIONS.minute
        time_now = MarketCandle.get_start_time(now() - datetime.timedelta(seconds=15), resolution)
        time_1h = time_now - datetime.timedelta(hours=1)
        time_1d = time_now - datetime.timedelta(days=1)
        time_7d = time_now - datetime.timedelta(days=7)
        for currency_name, currency in Currencies._identifier_map.items():
            if currency < Currencies.btc:
                continue
            stats = {
                'price': binance_prices.get(currency_name, 0),
                'volume': 0,
                'change1h': 0,
                'change1d': 0,
                'change7d': 0,
            }
            if currency in AVAILABLE_CRYPTO_CURRENCIES:
                market = Market.get_for(currency, RIAL)
                data_now = MarketCandle.get_candle(market, resolution, time_now)
                data_1h = MarketCandle.get_candle(market, resolution, time_1h)
                data_1d = MarketCandle.get_candle(market, resolution, time_1d)
                data_7d = MarketCandle.get_candle(market, resolution, time_7d)
                if data_now and data_1h and data_1d and data_7d:
                    stats['change1h'] = data_now.get_change_percent(data_1h)
                    stats['change1d'] = data_now.get_change_percent(data_1d)
                    stats['change7d'] = data_now.get_change_percent(data_7d)
            prices[currency_name.upper()] = stats
        response = json.dumps(serialize({
            'status': 'ok',
            'prices': prices,
            'params': {
                'USDTIRT': NobitexSettings.get_system_usd_price(),
                'USDTUSD': 1,
            }
        }), ensure_ascii=False)
        cache.set(response_cache_key, response, 10)
    return HttpResponse(response, content_type='application/json')


@method_decorator(ratelimit(key='user_or_ip', rate='300/1m', block=True), name='get')
class DepthChartAPI(PublicAPIView):
    def get(self, request, symbol):
        symbol = parse_symbol(symbol)
        asks, bids, last_trade_price = MarketDepthChartGenerator.get_chart(market_symbol=symbol)
        response = {
            "status": "ok",
            "lastUpdate": MarketDepthChartGenerator.get_last_update_date(symbol),
            "bids": bids,
            "asks": asks,
            "lastTradePrice": last_trade_price
        }

        return JsonResponse(response)


class UsersFavoriteMarkets(APIView):
    """
    see: https://bitex-doc.nobitex.ir/doc/favoritemarkets-ON32WGZrlF
    """

    @method_decorator(ratelimit(key='user_or_ip', rate='6/m', method='GET', block=True))
    def get(self, request):
        """
        GET /users/markets/favorite
        """
        # Log app version
        if not settings.ONLY_REPLICA and random.random() <= settings.SET_USER_PROPERTIES_PR:  # noqa: S311
            UserProfileManager.set_client_version_from_ua(request.user, request.headers.get('user-agent'))
        user_favorite_markets = UserMarketsPreferences.get_favorite_markets(request.user)
        return self.response(
            HttpResponse(
                '{' + '"status": "ok", "favoriteMarkets":' + user_favorite_markets + '}',
                content_type='application/json',
            )
        )

    @method_decorator(ratelimit(key='user_or_ip', rate='12/m', method='POST', block=True))
    def post(self, request):
        """
        Set and change favorite markets of user
        POST /users/markets/favorite
        parameter: market: "BTCIRT" or "BTCIRT,BTCUSDT,ETHIRT"
        Response:
        {
            "status": "ok",
            "favoriteMarkets": ["BTCIRT", "DOGEIRT"],
        }
        """
        user = request.user
        try:
            user_favorite_markets = UserMarketsPreferences.set_favorite_market(user, self.g('market'))
        except ParseMarketError as pe:
            return JsonResponse({
                'status': 'failed',
                'code': 'InvalidData',
                'message': f'{str(pe)} is not a valid market!'
            }, status=HTTP_400_BAD_REQUEST)
        except ValueError:
            return JsonResponse({
                'status': 'failed',
                'code': 'InvalidData',
                'message': 'market is necessary',
            }, status=HTTP_400_BAD_REQUEST)
        except InternalError:
            if random.random() < 0.1:
                report_exception()

        return self.response({
            'status': 'ok',
            'favoriteMarkets': user_favorite_markets,
        })

    @method_decorator(ratelimit(key='user_or_ip', rate='12/m', method='DELETE', block=True))
    def delete(self, request):
        """
        DELETE /users/markets/favorite
        parameter(optional): market: "BTCIRT"
        If you send specific market symbol it would be removed from FavoriteMarkets' list
        But it deletes all favorite markets of user without parameter
        """
        market = self.request.data.get('market')
        try:
            user_favorite_markets = UserMarketsPreferences.remove_favorite_market(request.user, market)
        except ParseMarketError as pe:
            return JsonResponse({
                'status': 'failed',
                'code': 'InvalidData',
                'message': f'{str(pe)} is not a valid market!'
            }, status=HTTP_400_BAD_REQUEST)
        except ValueError:
            return JsonResponse({
                'status': 'failed',
                'code': 'InvalidData',
                'message': 'market is necessary (All or MarketSymbol)',
            }, status=HTTP_400_BAD_REQUEST)
        return self.response({
            'status': 'ok',
            'favoriteMarkets': user_favorite_markets,
        })


class UsersFavoriteMarketsList(UsersFavoriteMarkets):
    """
    see: https://bitex-doc.nobitex.ir/doc/favoritemarkets-ON32WGZrlF
    """

    @method_decorator(ratelimit(key='user_or_ip', rate='6/m', method='GET', block=True))
    def get(self, request):
        """
        GET /users/markets/favorite/list
        """
        # Log app version
        if not settings.ONLY_REPLICA and random.random() <= settings.SET_USER_PROPERTIES_PR:  # noqa: S311
            UserProfileManager.set_client_version_from_ua(request.user, request.headers.get('user-agent'))
        user_favorite_markets = UserMarketsPreferences.get_favorite_markets(request.user)
        return self.response(
            HttpResponse(
                '{' + '"status": "ok", "favoriteMarkets":' + user_favorite_markets + '}',
                content_type='application/json',
            )
        )

    def post(self, request):
        raise Http404()

    def delete(self, request):
        raise Http404()


class OpenOrderCountView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='15/1m', method='GET', block=True))
    def get(self, request):
        """API for open orders count

        GET /market/orders/open-count
        """
        trade_type = parse_order_trade_type(self.g('tradeType'))

        open_orders = (
            Order.objects.filter(user=request.user, status__in=(Order.STATUS.active, Order.STATUS.inactive))
            .exclude(pair__isnull=False, status=Order.STATUS.inactive)
            .exclude(channel=Order.CHANNEL.system_block)
        )
        if trade_type:
            open_orders = open_orders.filter(trade_type=trade_type)

        return self.response(
            {
                'status': 'ok',
                'count': open_orders.count(),
            }
        )
