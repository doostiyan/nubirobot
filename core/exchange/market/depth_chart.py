import json
import logging
from decimal import Decimal
from multiprocessing import Pool
from typing import List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from exchange.base.decorators import measure_time
from exchange.base.models import PRICE_PRECISIONS, VALID_MARKET_SYMBOLS
from exchange.base.serializers import serialize_timestamp
from exchange.market.orderbook import OrderBook, OrderBookGenerator

logger = logging.getLogger(__name__)

DEPTH_CHART_PRICE_PRECISIONS = {
    'BTCIRT': Decimal('1000'),
    'ETHIRT': Decimal('1000'),
    'LTCIRT': Decimal('100'),
    'XRPIRT': Decimal('100'),
    'BCHIRT': Decimal('10'),
    'USDTIRT': Decimal('10'),
    'BNBIRT': Decimal('10'),
    'EOSIRT': Decimal('10'),
    'XLMIRT': Decimal('10'),
    'ETCIRT': Decimal('10'),
    'TRXIRT': Decimal('10'),
    'PMNIRT': Decimal('10'),
    'DOGEIRT': Decimal('1'),
    'ADAIRT': Decimal('10'),
    'LINKIRT': Decimal('10'),
    'DAIIRT': Decimal('10'),
    'DOTIRT': Decimal('10'),
    'UNIIRT': Decimal('10'),
    'AAVEIRT': Decimal('10'),
    'GRTIRT': Decimal('10'),
    'SHIBIRT': Decimal('10'),
    'FILIRT': Decimal('10'),
    'MATICIRT': Decimal('10'),
    'SOLIRT': Decimal('10'),
    'THETAIRT': Decimal('10'),
    'AVAXIRT': Decimal('10'),
    'FTMIRT': Decimal('10'),
    'AXSIRT': Decimal('10'),
    'MANAIRT': Decimal('10'),
    'SANDIRT': Decimal('10'),
    'ONEIRT': Decimal('10'),

    'ADAUSDT': Decimal('1e-3'),
    'GRTUSDT': Decimal('1e-4'),
    'FILUSDT': Decimal('1e-2'),
    'FTMUSDT': Decimal('1e-3'),
}


class DepthChartOrderBook(OrderBook):
    MAX_BOOK_ITEMS = 1000

    @property
    def price_precision(self):
        symbol_price_precision = DEPTH_CHART_PRICE_PRECISIONS.get(self.symbol)
        if symbol_price_precision is not None:
            return -symbol_price_precision.adjusted()
        return -PRICE_PRECISIONS.get(self.symbol, Decimal('1E-8')).adjusted()


class MarketDepthChartGenerator:
    CACHE_TIMEOUT = None if settings.DEBUG else 30

    def __init__(self, market_symbol: str, sell_orders: List[List[str]], buy_orders: List[List[str]], last_trade_price: str):
        self.market_symbol = market_symbol
        self.sell_orders = sell_orders
        self.buy_orders = buy_orders
        self.last_trade_price = Decimal(last_trade_price.strip() or '0') if last_trade_price else Decimal('0')

    @classmethod
    @measure_time(metric='depth_chart_all_round')
    def run(cls, pool: Optional[Pool] = None):
        if pool:
            pool.map(cls.generate_chart_for_symbol, VALID_MARKET_SYMBOLS, 1)
        else:
            for symbol in VALID_MARKET_SYMBOLS:
                cls.generate_chart_for_symbol(market_symbol=symbol)

    @classmethod
    def get_chart(cls, market_symbol: str) -> Tuple[List[List[str]], List[List[str]], str]:
        cached_chart = cache.get(cls._get_cache_key(market_symbol))
        if not cached_chart:
            logger.warning("Cached depth chart data not available.")
            if settings.IS_TESTNET or settings.IS_TEST_RUNNER:
                chart = cls.generate_chart_for_symbol(market_symbol)
            else:
                chart = {"ask": [], "bid": [], "last_trade_price": "0"}
        else:
            chart = json.loads(cached_chart)
        return chart.get("ask"), chart.get("bid"), chart.get("last_trade_price")

    @classmethod
    def generate_chart_for_symbol(cls, market_symbol: str) -> dict:
        total_orders, total_skips, sell_orders, buy_orders, last_trade_price = (
            OrderBookGenerator.get_depth_chart_orderbook_for_market(market_symbol=market_symbol)
        )
        generator = cls(market_symbol, sell_orders=sell_orders, buy_orders=buy_orders, last_trade_price=last_trade_price)
        ask = generator.get_ask_chart()
        bid = generator.get_bid_chart()
        depth_chart = dict(ask=ask, bid=bid, last_trade_price=last_trade_price)

        depth_chart_update_details = dict(
            update_time=cls._get_update_time(), total_orders=total_orders, total_skips=total_skips)
        cache.set(cls._get_last_update_details_cache_key(market_symbol), json.dumps(depth_chart_update_details),
                  cls.CACHE_TIMEOUT)
        cache.set(cls._get_cache_key(market_symbol), json.dumps(depth_chart), cls.CACHE_TIMEOUT)
        return depth_chart

    def get_ask_chart(self):
        return self._calculate_chart_data(self.sell_orders)

    def get_bid_chart(self):
        return list(reversed(self._calculate_chart_data(self.buy_orders)))

    def _calculate_chart_data(self, orders: List[List[str]]) -> List[list]:
        """
        This method takes a list of book orders, adds all the amounts together and returns a cumulative list of
        prices and amounts.
        >>> MarketDepthChartGenerator._calculate_chart_data([["1000", "0.1"], ["2000", "0.2"], ["3000", "0.3"]])
        [[1000, 0.1], [2000, 0.3], [3000, 0.6]]
        """
        depth = list()
        for order in orders:
            depth.append([Decimal(order[0]), Decimal(order[1])])
        depth = self._remove_outliers(depth)
        self._cumulate_amounts(depth)
        return [[str(d[0]), str(d[1])] for d in depth]

    def _remove_outliers(self, book_orders: List[List[Decimal]]):
        outlier_upper_limit = self.last_trade_price * 2
        outlier_lower_limit = self.last_trade_price / 2
        return list(filter(lambda order: outlier_lower_limit <= order[0] <= outlier_upper_limit, book_orders))

    @staticmethod
    def _cumulate_amounts(orders: List[List[Decimal]]):
        total_available = Decimal(0)
        for order in orders:
            order[1] = order[1] + total_available
            total_available = order[1]

    @staticmethod
    def _get_update_time():
        return str(serialize_timestamp(timezone.now()))

    @staticmethod
    def _get_cache_key(market_symbol: str):
        return f'depth_chart_{market_symbol}'

    @staticmethod
    def _get_last_update_details_cache_key(symbol: str):
        return f'depth_chart_{symbol}_update_details'

    @classmethod
    def get_last_update_date(cls, symbol: str) -> str:
        details = json.loads(cache.get(cls._get_last_update_details_cache_key(symbol)) or '{}')
        return details.get('update_time', '')
