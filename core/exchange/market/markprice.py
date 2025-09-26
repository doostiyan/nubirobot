import dataclasses
import datetime
from decimal import Decimal
from typing import ClassVar, Optional, Tuple

import requests
from django.conf import settings
from django.core.cache import cache

from exchange.accounts.models import Notification
from exchange.base.calendar import ir_now, ir_tz
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.constants import ZERO
from exchange.base.helpers import CacheItem
from exchange.base.logging import metric_incr, report_exception
from exchange.base.models import (
    PRICE_PRECISIONS,
    Currencies,
    Settings,
    get_currency_codename_binance,
    get_market_symbol,
)
from exchange.market.models import Market

PRICE_EXPIRATION = datetime.timedelta(minutes=1)


class Exchange:
    last_update: Optional[datetime.datetime] = None
    name: str
    weight: int

    @dataclasses.dataclass
    class Price:
        exchange: 'Exchange'
        value: Decimal

        def is_valid(self):
            if not self.value:
                return False
            if not self.exchange.last_update:
                return False
            return (ir_now() - self.exchange.last_update) <= PRICE_EXPIRATION

        @property
        def weight(self):
            return self.exchange.weight

        def adjust(self, valid_range: Tuple[Decimal, Decimal]):
            """Adjust the price value to fit in valid range

            Args:
                valid_range: a tuple of (min, max) acceptable values
            """
            if self.value < valid_range[0]:
                self.value = valid_range[0]
            elif self.value > valid_range[1]:
                self.value = valid_range[1]

        def get_spread(self, price: 'Exchange.Price') -> int:
            """Return the spread between self and the given price

            Spread refers to the difference or gap between two prices.
            Args:
                price: the price to calculate the spread upon

            Returns:
                the spread as rounded percent
            """
            return round((self.value / price.value - 1) * 100)

        def __repr__(self):
            return f'<{self.exchange.name}: {self.value.normalize():,f}>'

    def get_price(self, src_currency) -> Price:
        return self.Price(self, self._get_price(src_currency) or ZERO)

    def _get_price(self, src_currency) -> Optional[Decimal]:
        raise NotImplementedError


class ExternalExchange(Exchange):
    base_url = 'https://cdn.nobitex.ir/data/prices/'

    def __init__(self):
        self.prices, self.last_update = self.get_prices()

    @classmethod
    def _get_base_url(cls):
        if not settings.IS_TESTNET:
            return cls.base_url

        base_url = Settings.get_value('testnet_external_exchange_prices_base_url') or cls.base_url
        if not base_url.endswith('/'):
            base_url += '/'

        return base_url

    @classmethod
    def get_prices(cls) -> Tuple[dict, Optional[datetime.datetime]]:
        prices = {'usdt': Decimal('1')}
        last_update = None
        try:
            response = requests.get(f'{cls._get_base_url()}{cls.name}-spot.json', timeout=5)
            response.raise_for_status()
            for item in response.json():
                if item['symbol'].endswith('USDT'):
                    prices[item['symbol'][:-4].lower()] = Decimal(item['price'])
                if item['symbol'].startswith('USDT'):
                    prices[item['symbol'][4:].lower()] = 1 / Decimal(item['price'])
                if item['symbol'] == 'LASTUPDATE':
                    last_update = datetime.datetime.fromtimestamp(int(item['price']), tz=ir_tz())
            if not last_update:
                raise ValueError('No last update in CDN prices response')
            if (ir_now() - last_update) > PRICE_EXPIRATION:
                metric_incr('metric_cdn_prices_error_total', labels=('OutdatedData', 0, cls.name))
        except requests.RequestException as e:
            error_name = e.__class__.__name__
            status_code = getattr(e.response, 'status_code', 0)
            metric_incr('metric_cdn_prices_error_total', labels=(error_name, status_code, cls.name))
        except:
            metric_incr('metric_cdn_prices_error_total', labels=('UnexpectedError', 0, cls.name))
            report_exception()
        return prices, last_update

    def _get_price(self, src_currency) -> Optional[Decimal]:
        currency_code = str(get_currency_codename_binance(src_currency, ignore_logical_changes=False)).split('_')[-1]
        price = self.prices.get(currency_code)
        if price:
            scale = Decimal(CURRENCY_INFO.get(src_currency, {}).get('scale', '1'))
            price *= scale
        return price


class BinanceExchange(ExternalExchange):
    name = 'binance'
    weight = 45

class OKXExchange(ExternalExchange):
    name = 'okx'
    weight = 45


class InternalExchange(Exchange):
    name = 'nobitex'
    weight = 10
    dst_currency = Currencies.usdt

    def _get_price(self, src_currency) -> Optional[Decimal]:
        if src_currency == self.dst_currency:
            return Decimal('1')

        symbol = get_market_symbol(src_currency, self.dst_currency)

        _cache_keys = {
            'best_sell': f'orderbook_{symbol}_best_active_sell',
            'best_buy': f'orderbook_{symbol}_best_active_buy',
            'last_update': f'orderbook_{symbol}_update_time',
        }
        _cache_data = cache.get_many(_cache_keys.values())
        update_timestamp = _cache_data.pop(_cache_keys['last_update'], None)
        if update_timestamp:
            self.last_update = datetime.datetime.fromtimestamp(int(update_timestamp) / 1000, tz=ir_tz())
        else:
            self.last_update = None
        prices = [Decimal(price) for price in _cache_data.values() if price]
        if prices:
            mean = sum(prices, start=ZERO) / len(prices)
            return mean.quantize(PRICE_PRECISIONS.get(symbol))


class MarkPriceCalculator:
    PRICE_VARIATION_COEFFICIENT = Decimal('0.05')
    CACHE_KEY = 'mark_price_{src_currency}'

    _usdt_market: Market

    class SpreadCache(CacheItem):
        key = 'mark_price_spread_cache'
        default: ClassVar[dict] = {}

    def __init__(self):
        self.exchanges = (BinanceExchange(), OKXExchange(), InternalExchange())
        self._spread_cache = self.SpreadCache()

    def get_valid_price_range(self, center: Decimal) -> Tuple[Decimal, Decimal]:
        return (1 - self.PRICE_VARIATION_COEFFICIENT) * center, (1 + self.PRICE_VARIATION_COEFFICIENT) * center

    def calculate_mark_price(self, src_currency) -> Optional[Decimal]:
        prices = [exchange.get_price(src_currency) for exchange in self.exchanges]
        prices = sorted(filter(lambda p: p.is_valid(), prices), key=lambda p: p.value)
        if not prices:
            return None
        symbol = get_market_symbol(src_currency, Currencies.usdt)
        median_price = prices[len(prices) // 2]
        if len(prices) == 2:
            median_price = max(prices, key=lambda p: p.weight)
        valid_range = self.get_valid_price_range(center=median_price.value)
        for price in prices:
            if price != median_price:
                self.log_price_spread(symbol, price, median_price)
                price.adjust(valid_range)
        mean = sum((price.value * price.weight for price in prices), start=ZERO) / sum(price.weight for price in prices)
        return mean.quantize(PRICE_PRECISIONS.get(symbol, Decimal('1E-8')))

    def set_mark_price(self, src_currency: int):
        mark_price = self.calculate_mark_price(src_currency)
        if not mark_price:
            return
        cache.set(
            self.CACHE_KEY.format(src_currency=src_currency), mark_price, timeout=PRICE_EXPIRATION.total_seconds()
        )

    @classmethod
    def get_usdt_market_price(cls):
        if not hasattr(cls, '_usdt_market'):
            cls._usdt_market = Market.get_for(Currencies.usdt, Currencies.rls)
        return cls._usdt_market.get_last_trade_price()

    @classmethod
    def get_mark_price(cls, src_currency: int, dst_currency: int) -> Optional[Decimal]:
        usdt_mark_price = cache.get(cls.CACHE_KEY.format(src_currency=src_currency))
        if usdt_mark_price and dst_currency == Currencies.rls:
            usdt_price = cls.get_usdt_market_price()
            if not usdt_price:
                return None
            precision = PRICE_PRECISIONS.get(get_market_symbol(src_currency, dst_currency), Decimal('1E-8'))
            return (usdt_price * usdt_mark_price).quantize(precision)
        return usdt_mark_price

    @classmethod
    def delete_mark_price(cls, src_currency: int) -> bool:
        return cache.delete(cls.CACHE_KEY.format(src_currency=src_currency))

    def log_price_spread(self, symbol: str, price: Exchange.Price, median_price: Exchange.Price):
        spread = price.get_spread(median_price)
        if not abs(spread):
            return
        metric_incr('metric_mark_price_spread_count', labels=(price.exchange.name, symbol))
        metric_incr('metric_mark_price_spread_sum', abs(spread), labels=(price.exchange.name, symbol))
        spread_key = (symbol, price.exchange.name)
        if abs(spread) > 3 and spread > self._spread_cache.value.get(spread_key, 0):
            self._spread_cache.value[spread_key] = spread
            Notification.notify_admins(
                message=f'Market: {symbol}\nSpread between {price} and {median_price} is {spread}%',
                title='Mark Price Spread',
                channel='mark_price',
            )

    @classmethod
    def clear_spread_cache(cls):
        cls.SpreadCache.clear()
