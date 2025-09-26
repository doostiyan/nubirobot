import json

from flask import Blueprint
from flask.views import View

from nobitex.api import cache
from nobitex.api.base import get_data, parse_symbol, parse_currency, create_response, VALID_MARKET_SYMBOLS, CURRENCIES

market_app = Blueprint('market', __name__)


def cache_failure_response():
    response = '{"status":"failed","code":"UnexpectedError","message":"We cannot proceed with your request."}'
    return create_response(response, cors='https://nobitex.ir', status=500)


@market_app.route('/v2/orderbook', methods=['POST'])
def orderbook():
    data = get_data()
    symbol = parse_symbol(data.get('symbol'))

    orderbook_bids = cache.get('orderbook_{}_bids'.format(symbol), '[]')
    orderbook_asks = cache.get('orderbook_{}_asks'.format(symbol), '[]')
    response = f'{{"status":"ok","bids":{orderbook_bids},"asks":{orderbook_asks}}}'
    return create_response(response)


class OrderBook(View):
    BIDS_KEY = 'bids'
    ASKS_KEY = 'asks'

    def dispatch_request(self, symbol):
        symbols: set = VALID_MARKET_SYMBOLS if symbol == 'all' else {parse_symbol(symbol)}

        data = self.get_cache_data(symbols)
        if not data:
            return cache_failure_response()

        response = '{"status":"ok"'
        if len(symbols) == 1:
            encoded_data = self.encode_market_orderbook(symbol, data)
            if not encoded_data:
                return cache_failure_response()
            response += f',{encoded_data}'
        else:
            for symbol in symbols:
                encoded_data = self.encode_market_orderbook(symbol, data)
                if encoded_data:
                    response += f',"{symbol}":{{{encoded_data}}}'
        response += '}'
        return create_response(response, max_age='1,public,stale-if-error=60', cors='https://nobitex.ir')

    @staticmethod
    def get_cache_data(symbols: set) -> dict:
        keys = [
            f'orderbook_{symbol}_{param}'
            for symbol in symbols
            for param in ('bids', 'asks', 'update_time', 'last_trade_price')
        ]
        return cache.get_many(keys)

    @classmethod
    def encode_market_orderbook(cls, symbol: str, data: dict) -> str:
        orderbook_bids = data.get(f'orderbook_{symbol}_asks')  # The cache key has terminology issue.
        orderbook_asks = data.get(f'orderbook_{symbol}_bids')  # So does this one.
        last_update = data.get(f'orderbook_{symbol}_update_time')
        last_trade_price = data.get(f'orderbook_{symbol}_last_trade_price')
        if not all((orderbook_bids, orderbook_asks, last_update)):
            return ''
        return (
            f'"lastUpdate":{last_update},'
            f'"lastTradePrice":"{last_trade_price}",'
            f'"{cls.BIDS_KEY}":{orderbook_bids},'
            f'"{cls.ASKS_KEY}":{orderbook_asks}'
        )


class DepthChartAPI(View):
    CHART_CACHE_KEY = 'depth_chart_{}'
    DETAILS_CACHE_KEY = 'depth_chart_{}_update_details'

    def dispatch_request(self, symbol):
        symbol = parse_symbol(symbol)
        data = self.get_cache(symbol)
        asks, bids, last_trade_price = self.get_chart(data.get(self.CHART_CACHE_KEY.format(symbol), '{}'))
        response = {
            "status": "ok",
            "lastUpdate": self.get_last_update_date(data.get(self.DETAILS_CACHE_KEY.format(symbol), '{}')),
            "bids": bids,
            "asks": asks,
            "lastTradePrice": last_trade_price,
        }
        return create_response(json.dumps(response), max_age='1,public,stale-if-error=60', cors='https://nobitex.ir')

    def get_cache(self, symbol):
        return cache.get_many([self.CHART_CACHE_KEY.format(symbol), self.DETAILS_CACHE_KEY.format(symbol)])

    @staticmethod
    def get_chart(chart_data):
        chart = json.loads(chart_data)
        return chart.get("ask", []), chart.get("bid", []), chart.get("last_trade_price", "0")

    @staticmethod
    def get_last_update_date(details_value):
        details = json.loads(details_value)
        return details.get('update_time', '')


class OldOrderBook(OrderBook):
    """Old order book with terminology issue for backward-compatibility"""
    BIDS_KEY = 'asks'
    ASKS_KEY = 'bids'


market_app.add_url_rule('/v2/orderbook/<symbol>', view_func=OldOrderBook.as_view('orderbook_v2'), methods=['GET'])
market_app.add_url_rule('/v3/orderbook/<symbol>', view_func=OrderBook.as_view('orderbook_v3'), methods=['GET'])
market_app.add_url_rule('/v2/depth/<symbol>', view_func=DepthChartAPI.as_view('depth_v2'), methods=['GET'])


@market_app.route('/v2/trades', methods=['POST'])
def trades():
    data = get_data()
    symbol = parse_symbol(data.get('symbol'))

    recent_trades = cache.get('trades_' + symbol, '[]')
    response = '{"status":"ok","trades":' + recent_trades + '}'
    return create_response(response)


@market_app.route('/v2/trades/<symbol>', methods=['GET'])
def trades_get(symbol):
    symbol = parse_symbol(symbol)
    recent_trades = cache.get('trades_' + symbol, '[]')
    response = '{"status":"ok","trades":' + recent_trades + '}'
    return create_response(response, max_age='5,public,stale-if-error=600', cors='https://nobitex.ir')


@market_app.route('/market/stats', methods=['GET', 'POST'])
def market_stats():
    data = get_data()
    sources = data.get('srcCurrency')
    sources = sources.split(',') if sources else [c for c, v in CURRENCIES.items() if v >= 10]
    destinations = data.get('dstCurrency')
    destinations = destinations.split(',') if destinations else ['rls', 'usdt']

    stats_cache_keys = {
        f'{src}-{dst}': f'market_stats_{parse_currency(src)}-{parse_currency(dst)}'
        for src in sources for dst in destinations if src != dst
    }
    stats_cache_items = cache.get_many(stats_cache_keys.values())

    stats = []
    for pair, cache_key in stats_cache_keys.items():
        market_stat = stats_cache_items.get(cache_key) or '{"isClosed":true,"isClosedReason":"NoData"}'
        stats.append(f'"{pair}":{market_stat}')

    # Global Binance Statistics
    stats_binance = cache.get('market_stats_binance', '{}')
    response = '{"status":"ok","stats":{' + ','.join(stats) + '},"global":{"binance":' + stats_binance + '}}'
    return create_response(response, max_age='10,public,stale-if-error=600', cors='https://nobitex.ir')
