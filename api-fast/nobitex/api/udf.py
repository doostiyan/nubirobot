import datetime
import json
import time
from decimal import Decimal

from flask import Blueprint
from flask.views import View

from nobitex.api import cache
from nobitex.api.base import create_response, parse_int, parse_symbol, get_data, called_from_frontend, \
    PRICE_PRECISIONS, VALID_MARKET_SYMBOLS

udf_app = Blueprint('udf', __name__, url_prefix='/market/udf')


def normalize_chart_symbol(symbol: str) -> str:
    symbol = (symbol or '').split(':')[-1].upper()
    return parse_symbol(symbol)


@udf_app.route('/time', methods=['GET', 'POST'])
def udf_time():
    response = str(int(time.time()))
    return create_response(response, cors=True)


class UDFConfig(View):
    UDF_CONFIG: str = json.dumps({
        'supports_time': True,
        'supports_search': True,
        'supports_group_request': False,
        'supports_marks': False,
        'supports_timescale_marks': False,
        'timezone': 'Asia/Tehran',
        'supported_resolutions': ['1', '5', '15', '30', '60', '180', '240', '360', '720', '1D', '2D', '3D'],
        'exchanges': [
            {'value': '', 'name': 'All Exchanges', 'desc': ''},
            {'value': 'Nobitex', 'name': 'Nobitex', 'desc': 'Nobitex'}
        ],
        'symbols_types': [
            {'name': 'All types', 'value': ''},
            {'name': 'Crypto Currency', 'value': 'crypto-currency'}
        ],
    })

    def dispatch_request(self):
        return create_response(self.UDF_CONFIG, max_age=3600, cors=True)


class UDFSymbol(View):
    def dispatch_request(self):
        data = get_data()
        symbol = normalize_chart_symbol(data.get('symbol'))
        response = cache.get(f'chart_{symbol}_info', '{}')
        return create_response(response, max_age=3600, cors=True)


class UDFHistory(View):
    UDF_RESOLUTIONS: dict = {
        '1': ('minute', 1),
        '5': ('minute', 5),
        '15': ('minute', 15),
        '30': ('minute', 30),
        '60': ('hour', 1),
        '180': ('hour', 3),
        '240': ('hour', 4),
        '360': ('hour', 6),
        '720': ('hour', 12),
        'D': ('day', 1),
        '1D': ('day', 1),
        '2D': ('day', 2),
        '3D': ('day', 3),
    }
    MAX_CANDLES: int = 500
    BUCKET_SIZE: int = 200

    def dispatch_request(self):
        data = get_data()
        symbol = normalize_chart_symbol(data.get('symbol'))
        resolution = data.get('resolution')
        dt_from = parse_int(data.get('from')) or 0
        dt_to = parse_int(data.get('to')) or 0
        count_back = parse_int(data.get('countback')) or 0
        page = parse_int(data.get('page')) or 1

        # Parse timeframe resolution
        if resolution not in self.UDF_RESOLUTIONS:
            response = '{"s":"error","errmsg":"Invalid resolution!"}'
            return create_response(response)

        unit, factor = self.UDF_RESOLUTIONS.get(resolution)
        timeframe = int(datetime.timedelta(**{f'{unit}s': factor}).total_seconds())

        # Paginate
        if called_from_frontend():
            self.MAX_CANDLES = 40_000
        dt_to -= self.MAX_CANDLES * timeframe * (page - 1)
        if count_back:
            dt_from = dt_to - min(count_back, self.MAX_CANDLES) * timeframe
        else:
            dt_from = max(dt_from, dt_to - self.MAX_CANDLES * timeframe)

        # Parse date range
        dt_to = self.next_start_time(dt_to, timeframe)
        dt_from = self.next_start_time(dt_from, timeframe)

        if dt_from > dt_to:
            return create_response('{"s":"no_data"}', cors=True)

        times, opens, highs, lows, closes, volumes = self.get_history(symbol, dt_from, dt_to, resolution)

        if not times:
            return create_response('{"s":"no_data"}', cors=True)

        response = json.dumps({
            's': 'ok', 't': times, 'o': opens, 'h': highs, 'l': lows, 'c': closes, 'v': volumes
        })
        return create_response(response, cors=True)

    @classmethod
    def get_history(cls, symbol: str, dt_from: int, dt_to: int, resolution: str) -> tuple:
        unit, factor = cls.UDF_RESOLUTIONS.get(resolution)
        candle_duration = int(datetime.timedelta(**{f'{unit}s': 1}).total_seconds())
        count = (dt_to - dt_from) // candle_duration

        result_values = [], [], [], [], [], []
        if count <= 10 and abs(time.time() - dt_to) < 10:
            # Seek short-term cache
            key = f'marketdata_{symbol}_{unit}_short'
            data = cache.get(key)
            if data:
                cls.add_to_result(result_values, data, dt_from, dt_to)
        else:
            # Seek long-term cache
            bucket_length = cls.BUCKET_SIZE * candle_duration
            bucket = cls.get_bucket(dt_from, bucket_length)
            while bucket < dt_to:
                key = f'marketdata_{symbol}_{unit}_{bucket}'
                data = cache.get(key)
                if data:
                    cls.add_to_result(result_values, data, dt_from, dt_to)
                bucket += bucket_length

        if factor > 1:
            result_values = cls.aggregate_result(result_values, dt_from, candle_duration * factor)
        cls.normalize_result(result_values, symbol, is_rial=symbol.endswith('IRT'))
        return result_values

    @staticmethod
    def add_to_result(result_values: tuple, cache_data: dict, dt_from: int, dt_to: int):
        if dt_to < cache_data['time'][0] or dt_from > cache_data['time'][-1]:
            return
        from_index = cache_data['time'].index(dt_from) if dt_from in cache_data['time'] else 0
        to_index = cache_data['time'].index(dt_to) if dt_to in cache_data['time'] else len(cache_data['time'])
        index_slice = slice(from_index, to_index)

        times, opens, highs, lows, closes, volumes = result_values
        times.extend(cache_data['time'][index_slice])
        opens.extend(cache_data['open'][index_slice])
        highs.extend(cache_data['high'][index_slice])
        lows.extend(cache_data['low'][index_slice])
        closes.extend(cache_data['close'][index_slice])
        volumes.extend(cache_data['volume'][index_slice])

    @classmethod
    def aggregate_result(cls, result_values: tuple, dt: int, timeframe: int) -> tuple:
        times, opens, highs, lows, closes, volumes = result_values
        n_times, n_opens, n_highs, n_lows, n_closes, n_volumes = [], [], [], [], [], []
        i = j = 0
        while i < len(times):
            next_dt = cls.next_start_time(dt + 1, timeframe)
            while j < len(times) and times[j] < next_dt:
                j += 1
            if j > i:
                n_times.append(dt)
                n_opens.append(opens[i])
                n_highs.append(max(highs[i:j]))
                n_lows.append(min(lows[i:j]))
                n_closes.append(closes[j - 1])
                n_volumes.append(round(sum(volumes[i:j]), 8))  # Round to fix float sum bug :/
            dt = next_dt
            i = j
        return n_times, n_opens, n_highs, n_lows, n_closes, n_volumes

    @staticmethod
    def normalize_result(result_values: tuple, symbol: str, is_rial: bool):
        times, opens, highs, lows, closes, volumes = result_values
        precision = -PRICE_PRECISIONS.get(symbol, Decimal('1e-2')).adjusted()
        for prices in (opens, highs, lows, closes):
            for i in range(len(prices)):
                prices[i] = round(prices[i], precision)
                if is_rial:
                    prices[i] /= 10

    @staticmethod
    def get_bucket(timestamp: int, bucket_length: int) -> int:
        return timestamp - timestamp % bucket_length

    @staticmethod
    def next_start_time(timestamp: int, timeframe: int) -> int:
        result = timestamp + -(timestamp + time.localtime(timestamp).tm_gmtoff) % timeframe
        if result - timestamp > 3600:
            fixed_result = result + (time.localtime(timestamp).tm_isdst - time.localtime(result).tm_isdst) * 3600
            if time.localtime(fixed_result).tm_isdst == time.localtime(result).tm_isdst:
                return fixed_result
        return result


class UDFSearch(View):
    def dispatch_request(self):
        data = get_data()
        tp = data.get('type')
        exchange = data.get('exchange')
        query = data.get('query', '', type=str).lower()
        limit = data.get('limit', 30, type=int)

        search_info = json.loads(cache.get(f'chart_search_info', '[]'))
        search_results = [
            {
                'symbol': symbol_info['name'],
                'full_name': symbol_info['name'],
                'description': symbol_info['description'],
                'exchange': symbol_info['exchange'],
                'ticker': symbol_info['ticker'],
                'type': symbol_info['type'],
            }
            for symbol_info in search_info
            if self.match_filter(symbol_info, query, tp, exchange)
        ]
        response = json.dumps(search_results[:limit])
        return create_response(response, max_age=3600, cors=True)

    @staticmethod
    def match_filter(symbol_info: dict, query: str, tp: str, exchange: str) -> bool:
        if not symbol_info:
            return False
        if query and query not in symbol_info['name'].lower() and query not in symbol_info['description'].lower():
            return False
        if tp and tp != symbol_info['type']:
            return False
        if exchange and exchange != symbol_info['exchange']:
            return False
        return symbol_info['name'] in VALID_MARKET_SYMBOLS


class UDFStub(View):
    def __init__(self, response: str):
        self.response = response

    def dispatch_request(self):
        return create_response(self.response, max_age=3600, cors=True)


udf_app.add_url_rule('/config', view_func=UDFConfig.as_view('config'), methods=['GET'])
udf_app.add_url_rule('/history', view_func=UDFHistory.as_view('history'), methods=['GET'])
udf_app.add_url_rule('/time', view_func=udf_time, methods=['GET'])
udf_app.add_url_rule('/symbols', view_func=UDFSymbol.as_view('symbols'), methods=['GET'])
udf_app.add_url_rule('/search', view_func=UDFSearch.as_view('search'), methods=['GET'])
udf_app.add_url_rule('/quotes', view_func=UDFStub.as_view('quotes', '{}'), methods=['GET', 'POST'])
