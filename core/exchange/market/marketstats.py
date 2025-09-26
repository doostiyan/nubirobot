""" Market Statistics & Prices
"""
import datetime
import json
import time
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache, caches

from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings, get_currency_codename
from exchange.base.serializers import serialize
from exchange.market.markprice import MarkPriceCalculator
from exchange.market.models import Market, MarketCandle, SymbolInfo

from ..base.constants import ZERO
from ..base.publisher import all_market_stats_publisher, market_stats_publisher
from .inspector import get_orders_stats


class MarketStats:
    """ Utilities to calculate market price and other statistics """

    @classmethod
    def set_caches(cls, key, value, timeout=None):
        for c in (caches['default'], caches['chart_api']):
            c.set(key, value, timeout)

    @classmethod
    def calculate_market_stats(cls, market: Market):
        """ Calculate and cache latest market OHLC data """
        # Date range
        yesterday = ir_now() - datetime.timedelta(days=1)

        # Market Stats - Saved
        today_data = market.marketcandle_set.filter(
            resolution=MarketCandle.RESOLUTIONS.hour, start_time__gte=yesterday
        ).order_by('start_time')
        volume_src = Decimal('0')
        volume_dst = Decimal('0')
        day_low = Decimal('0')
        day_high = Decimal('0')
        day_open = None
        day_close = Decimal('0')
        for data in today_data:
            volume_src += data.trade_amount
            volume_dst += data.trade_total
            if data.low_price > Decimal('0'):
                if data.low_price < day_low or day_low <= Decimal('0'):
                    day_low = data.low_price
            day_high = max(day_high, data.high_price)
            day_open = day_open or data.open_price
            day_close = data.close_price or day_close

        # Orders Stats
        orders_stats = get_orders_stats(market)

        # Growth Rate
        if day_open:
            day_change = (day_close - day_open) / day_open
            day_change = (day_change * Decimal('100')).quantize(Decimal('1.00'))
        else:
            day_open = Decimal('0')
            day_change = Decimal('0')

        # Normalize stats
        if settings.IS_PROD and market.src_currency != Currencies.btc:
            volume_src /= 4
            volume_dst /= 4

        if settings.IS_PROD and market.src_currency == Currencies.usdt and market.dst_currency == Currencies.rls:
            volume_src /= 5
            volume_dst /= 5
        mark_price = MarkPriceCalculator.get_mark_price(market.src_currency, market.dst_currency) or ZERO

        # Cache and return data
        market_stats_data = serialize(
            {
                'isClosed': not market.is_active,
                'bestSell': orders_stats['bestSell'],
                'bestBuy': orders_stats['bestBuy'],
                'volumeSrc': volume_src,
                'volumeDst': volume_dst,
                'latest': day_close,
                'mark': mark_price,
                'dayLow': day_low,
                'dayHigh': day_high,
                'dayOpen': day_open,
                'dayClose': day_close,
                'dayChange': day_change,
            }
        )

        if market.src_currency == Currencies.usdt and market.dst_currency == Currencies.rls:
            market_stats_data['volumeSrc'] = '0'
            market_stats_data['volumeDst'] = '0'
            market_stats_data['dayLow'] = '0'
            market_stats_data['dayHigh'] = '0'
            market_stats_data['dayOpen'] = '0'
            market_stats_data['dayClose'] = '0'
            market_stats_data['dayChange'] = '0'

        stats = json.dumps(
            market_stats_data,
            separators=(',', ':'),
        )
        cache.set('market_stats_{}-{}'.format(market.src_currency, market.dst_currency), stats)

        market_stats_publisher(market.symbol, stats)
        return stats

    @classmethod
    def calculate_market_stats_binance(cls):
        """ Calculate and cache crypto prices in Binance USDT markets """
        # TODO: use cache settings, and filter top coins
        stats_binance = json.dumps(Settings.get_dict('prices_binance'))
        cache.set('market_stats_binance', stats_binance)
        return stats_binance

    @classmethod
    def update_all_market_stats(cls):
        """ Cache stats for all markets """
        markets_count = 0
        time_start = time.time()

        all_stats = '{'
        for market in Market.objects.all().order_by('id'):
            market_stats = cls.calculate_market_stats(market)
            market_name = f'{get_currency_codename(market.src_currency)}-{get_currency_codename(market.dst_currency)}'
            all_stats += f'"{market_name}":{market_stats},'
            markets_count += 1
        all_stats = all_stats[:-1] + '}'
        all_market_stats_publisher(all_stats)
        cls.calculate_market_stats_binance()
        run_time = round((time.time() - time_start) * 1000)
        msg = 'MarketStats:  markets={}'.format(markets_count)
        print(msg.ljust(80) + '[{}ms]'.format(run_time))

    @classmethod
    def update_chart_config(cls):
        """ Update cache keys required for chart config APIs """
        # TODO: Cache common usages of history (if hit rate is high enough)
        time_start = time.time()
        for market in Market.objects.all():
            symbol = market.symbol
            cache_key = 'chart_{}_info'.format(symbol)
            try:
                symbol = SymbolInfo.objects.get(name=symbol)
            except SymbolInfo.DoesNotExist:
                symbol_info = '{}'
            else:
                symbol_info = json.dumps(symbol.to_json(), ensure_ascii=False)
            cls.set_caches(cache_key, symbol_info, 86400)
        search_list = SymbolInfo.objects.values('name', 'type', 'ticker', 'exchange', 'description').order_by('name')
        cls.set_caches('chart_search_info', json.dumps(list(search_list)), 86400)
        run_time = round((time.time() - time_start) * 1000)
        msg = 'ChartConfig:'
        print(msg.ljust(80) + '[{}ms]'.format(run_time))
