import json
import time
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.views.decorators.cache import cache_control
from django_ratelimit.decorators import ratelimit

from exchange.base.api import PublicAPIView, public_api
from exchange.base.decorators import cached_method
from exchange.base.helpers import called_from_frontend
from exchange.base.models import PRICE_PRECISIONS, Currencies
from exchange.base.parsers import parse_int
from exchange.market.models import Market, MarketCandle, SymbolInfo


@ratelimit(key='user_or_ip', rate='120/1m', method='GET', block=True)
@public_api
def udf_time(request):
    return HttpResponse(str(int(time.time())), content_type='application/json')


@ratelimit(key='user_or_ip', rate='120/1m', method='GET', block=True)
@cache_control(max_age=3600)
@public_api
def udf_config(request):
    return {
        'supports_search': True,
        'supports_group_request': False,
        'supported_resolutions': ['1', '5', '15', '30', '60', '180', '240', '360', '720', '1D', '2D', '3D'],
        'supports_marks': False,
        'supports_time': True,
        'supports_timescale_marks': False,
        'timezone': 'Asia/Tehran',
        'exchanges': [
            {
                'value': '',
                'name': 'All Exchanges',
                'desc': ''
            },
            {
                'value': 'Nobitex',
                'name': 'Nobitex',
                'desc': 'Nobitex'
            }
        ],
        'symbols_types': [
            {'name': 'All types', 'value': ''},
            {'name': 'Crypto Currency', 'value': 'crypto-currency'},
        ],
    }


@ratelimit(key='user_or_ip', rate='60/1m', method='GET', block=True)
@cache_control(max_age=3600)
@public_api
def udf_symbols(request):
    symbol = request.g('symbol')
    symbol = SymbolInfo.normalize(symbol)

    cache_key = 'chart_{}_info'.format(symbol)
    symbol_info = cache.get(cache_key)
    if not symbol_info:
        try:
            symbol = SymbolInfo.objects.get(name=symbol)
        except SymbolInfo.DoesNotExist:
            return {}
        symbol_info = json.dumps(symbol.to_json(), ensure_ascii=False)
        cache.set(cache_key, symbol_info, 600)
    return HttpResponse(symbol_info, content_type='application/json')


@ratelimit(key='user_or_ip', rate='60/1m', block=True)
@cache_control(max_age=3600)
@public_api
def udf_search(request):
    query = request.g('query')
    tp = request.g('type')
    exchange = request.g('exchange')
    limit = parse_int(request.g('limit'))
    query_is_empty = not query or len(query) == 0

    results = SymbolInfo.objects.all()
    if tp:
        results = results.filter(type__iexact=tp)
    if exchange:
        results = results.filter(exchange__iexact=exchange)
    if not query_is_empty:
        results = results.filter(Q(name__icontains=query) | Q(description__icontains=query))
    return [{
        'symbol': item.name,
        'full_name': item.name,
        'description': item.description,
        'exchange': item.exchange,
        'ticker': item.ticker,
        'type': item.type,
    } for item in results[:limit]]


class UDFHistory(PublicAPIView):
    UDF_RESOLUTIONS: dict = {
        '1': (MarketCandle.RESOLUTIONS.minute, 1),
        '5': (MarketCandle.RESOLUTIONS.minute, 5),
        '15': (MarketCandle.RESOLUTIONS.minute, 15),
        '30': (MarketCandle.RESOLUTIONS.minute, 30),
        '60': (MarketCandle.RESOLUTIONS.hour, 1),
        '180': (MarketCandle.RESOLUTIONS.hour, 3),
        '240': (MarketCandle.RESOLUTIONS.hour, 4),
        '360': (MarketCandle.RESOLUTIONS.hour, 6),
        '720': (MarketCandle.RESOLUTIONS.hour, 12),
        'D': (MarketCandle.RESOLUTIONS.day, 1),
        '1D': (MarketCandle.RESOLUTIONS.day, 1),
        '2D': (MarketCandle.RESOLUTIONS.day, 2),
        '3D': (MarketCandle.RESOLUTIONS.day, 3),
    }

    @method_decorator(ratelimit(key='user_or_ip', rate='60/m', method='GET', block=True))
    def get(self, request):
        # Parse resolution
        resolution = self.g('resolution')
        if resolution not in self.UDF_RESOLUTIONS:
            return self.response({
                's': 'error',
                'errmsg': 'Invalid resolution!'
            })
        base_resolution, factor = self.UDF_RESOLUTIONS.get(resolution)

        page = parse_int(self.g('page')) or 1

        # Parse date range
        timeframe = int(MarketCandle.resolution_to_timedelta(base_resolution).total_seconds()) * factor
        dt_to = parse_int(self.g('to')) - self.page_size * timeframe * (page - 1)
        dt_from = max(parse_int(self.g('from')) or 0, dt_to - self.page_size * timeframe)

        dt_to = self.next_start_time(dt_to, timeframe)
        dt_from = self.next_start_time(dt_from, timeframe)

        # Parse symbol
        symbol = SymbolInfo.normalize(self.g('symbol'))
        try:
            symbol = SymbolInfo.objects.get(name=symbol)
        except SymbolInfo.DoesNotExist:
            return self.response({
                's': 'error',
                'errmsg': 'Symbol not found!'
            })

        response = self.get_history(symbol.name, resolution, dt_from, dt_to)
        if not response or not response.get('t'):
            return self.response({'s': 'no_data'})

        return self.response({
            's': 'ok',
            **response
        })

    @classmethod
    @cached_method(timeout=15)
    def get_history(cls, symbol: str, resolution: str, dt_from: int, dt_to: int) -> dict:
        base_resolution, factor = cls.UDF_RESOLUTIONS.get(resolution)

        market = Market.by_symbol(symbol)
        candles = MarketCandle.objects.filter(
            market=market,
            resolution=base_resolution,
            start_time__gte=datetime.fromtimestamp(dt_from).astimezone(),
            start_time__lt=datetime.fromtimestamp(dt_to).astimezone(),
        ).order_by('start_time')

        results = cls.serialize_candles(candles)

        if factor:
            timeframe = int(MarketCandle.resolution_to_timedelta(base_resolution).total_seconds()) * factor
            results = cls.aggregate_result(results, dt_from, timeframe)

        is_rial = market and market.dst_currency == Currencies.rls
        cls.normalize_result(results, symbol, is_rial)

        return results

    @classmethod
    def aggregate_result(cls, results: dict, dt: int, timeframe: int) -> dict:
        aggregated_result = {key: [] for key in 'tohlcv'}
        i = j = 0
        while i < len(results['t']):
            next_dt = cls.next_start_time(dt + 1, timeframe)
            while j < len(results['t']) and results['t'][j] < next_dt:
                j += 1
            if j > i:
                aggregated_result['t'].append(dt)
                aggregated_result['o'].append(results['o'][i])
                aggregated_result['h'].append(max(results['h'][i:j]))
                aggregated_result['l'].append(min(results['l'][i:j]))
                aggregated_result['c'].append(results['c'][j - 1])
                aggregated_result['v'].append(sum(results['v'][i:j]))
            dt = next_dt
            i = j
        return aggregated_result

    @staticmethod
    def serialize_candles(candles: Iterable) -> dict:
        results = {key: [] for key in 'tohlcv'}
        for candle in candles:
            results['t'].append(candle.timestamp)
            results['o'].append(float(candle.public_open_price))
            results['h'].append(float(candle.public_high_price))
            results['l'].append(float(candle.public_low_price))
            results['c'].append(float(candle.public_close_price))
            results['v'].append(float(candle.trade_amount))
        return results

    @staticmethod
    def normalize_result(results: dict, symbol: str, is_rial: bool):
        """Apply precision and convert IRR to IRT"""
        precision = -PRICE_PRECISIONS.get(symbol, Decimal('1e-2')).adjusted()
        for key in 'ohlc':
            for i in range(len(results[key])):
                results[key][i] = round(results[key][i], precision)
                if is_rial:
                    results[key][i] /= 10

    @staticmethod
    def next_start_time(timestamp: int, timeframe: int) -> int:
        result = timestamp + -(timestamp + time.localtime(timestamp).tm_gmtoff) % timeframe
        if result - timestamp > 3600:
            fixed_result = result + (time.localtime(timestamp).tm_isdst - time.localtime(result).tm_isdst) * 3600
            if time.localtime(fixed_result).tm_isdst == time.localtime(result).tm_isdst:
                return fixed_result
        return result

    @cached_property
    def page_size(self) -> int:
        """Page size for items

        Trading View acts crazy on pagination while moving to past times.
        Using this, page size is increased for frontend api-calls, i.e. Trading View chart
        """
        if called_from_frontend(self.request):
            return 40_000
        return 500


@cache_control(max_age=3600)
@public_api
def udf_quotes(request):
    return {}
