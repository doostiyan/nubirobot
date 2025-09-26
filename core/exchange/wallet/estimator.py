""" Estimator Utilities """
from decimal import Decimal
from typing import List, Tuple

from django.core.cache import cache
from django.db.models import Q
from redis.exceptions import RedisError

from exchange.base.constants import ZERO
from exchange.base.decorators import SkipCache, ram_cache
from exchange.base.models import (
    AVAILABLE_MARKETS,
    PRICE_PRECISIONS,
    RIAL,
    TETHER,
    XCHANGE_CURRENCIES,
    get_market_symbol,
)
from exchange.market.models import Market
from exchange.market.orderbook import OrderBook, OrderBookGenerator
from exchange.xchange.constants import ALL_XCHANGE_PAIRS_CACHE_KEY, XCHANGE_PAIR_PRICES_CACHE_KEY
from exchange.xchange.models import MarketStatus


class PriceEstimator:
    """ Helper functions for estimating coin prices
    """

    @classmethod
    @ram_cache(timeout=10, default=(0, 0))
    def get_price_range(cls, currency: int, to_currency=RIAL, *, db_fallback=False) -> tuple:
        """ Return buy,sell price for the given currency

            Note: this method caches redis results for 10 seconds
        """
        if currency in XCHANGE_CURRENCIES or to_currency in XCHANGE_CURRENCIES:
            return XchangePriceEstimator.get_price_range(currency, to_currency, db_fallback=db_fallback)
        return MarketPriceEstimator.get_price_range(currency, to_currency, db_fallback=db_fallback)

    @classmethod
    def _get_value_by_best_price(cls, value, currency, to_currency, order_type, db_fallback, skip_cache):
        index = 0 if order_type == 'buy' else 1
        best_order_price = cls.get_price_range(currency, to_currency, db_fallback=db_fallback, skip_cache=skip_cache)[
            index
        ]
        return value * best_order_price

    @classmethod
    def get_rial_value_by_best_price(cls, value, currency, order_type, *, db_fallback=False, skip_cache=False):
        return int(cls._get_value_by_best_price(value, currency, RIAL, order_type, db_fallback, skip_cache))

    @classmethod
    def get_tether_value_by_best_price(cls, value, currency, order_type, *, db_fallback=False, skip_cache=False):
        return cls._get_value_by_best_price(value, currency, TETHER, order_type, db_fallback, skip_cache)


class MarketPriceEstimator:
    @classmethod
    def get_price_range(cls, currency: int, to_currency: int = RIAL, *, db_fallback=False) -> tuple:
        if currency == to_currency:
            return 1, 1
        if [currency, to_currency] in AVAILABLE_MARKETS:
            dst_currency = to_currency
        else:
            for pair in AVAILABLE_MARKETS:
                if pair[0] == currency and [pair[1], to_currency] in AVAILABLE_MARKETS:
                    dst_currency = pair[1]
                    break
            else:
                return 0, 0
        try:
            estimate_buy, estimate_sell = cls._get_prices_from_cache(currency, dst_currency)
        except RedisError as e:
            if not db_fallback:
                raise e
            estimate_buy, estimate_sell = cls._get_prices_from_db(currency, dst_currency)
        if dst_currency != to_currency:
            buy_conversion_ratio, sell_conversion_ratio = cls.get_price_range(dst_currency, to_currency)
            estimate_buy *= buy_conversion_ratio
            estimate_sell *= sell_conversion_ratio
        if not (estimate_buy or estimate_sell):
            raise SkipCache('Empty OrderBook')
        symbol = get_market_symbol(currency, to_currency)
        if precision := PRICE_PRECISIONS.get(symbol):
            estimate_buy = estimate_buy.quantize(precision)
            estimate_sell = estimate_sell.quantize(precision)
        return estimate_buy, estimate_sell

    @classmethod
    def _get_prices_from_cache(cls, src_currency: int, dst_currency: int) -> tuple:
        symbol = get_market_symbol(src_currency, dst_currency)
        cache_key_prefix = f'orderbook_{symbol}_'
        orderbook_params = ('best_buy', 'best_sell', 'best_active_buy', 'best_active_sell')
        values = cache.get_many(cache_key_prefix + param for param in orderbook_params)
        return cls._estimate_prices_based_on_orderbook_values(
            **{param: values.get(cache_key_prefix + param) or ZERO for param in orderbook_params}
        )

    @classmethod
    def _get_prices_from_db(cls, src_currency: int, dst_currency: int) -> tuple:
        market = Market.get_for(src_currency, dst_currency, skip_cache=True)
        sell_book = OrderBook('sell', market)
        buy_book = OrderBook('buy', market)
        OrderBookGenerator.skip_order_matches(sell_book, buy_book)
        return cls._estimate_prices_based_on_orderbook_values(
            best_buy=buy_book.best_price or ZERO,
            best_sell=sell_book.best_price or ZERO,
            best_active_buy=buy_book.best_active_price or ZERO,
            best_active_sell=sell_book.best_active_price or ZERO,
        )

    @staticmethod
    def _estimate_prices_based_on_orderbook_values(
        best_buy: Decimal, best_sell: Decimal, best_active_buy: Decimal, best_active_sell: Decimal
    ):
        if best_buy > best_sell > 0:
            mean = (best_active_buy + best_active_sell) / 2
            if best_buy == best_active_buy:
                return best_buy, mean
            if best_sell == best_active_sell:
                return mean, best_sell
            return mean, mean
        return best_active_buy, best_active_sell


class XchangePriceEstimator:
    @classmethod
    def get_price_range(cls, currency: int, to_currency: int = RIAL, *, db_fallback=False) -> Tuple[Decimal, Decimal]:
        """
        Getting the xchange price of a pair of currencies when at least one of currency or to_currency are traded
            only in xchange (== at least one of them is in XCHANGE_CURRENCIES)

        Any pair of currencies ever traded in xchange where at least one of them is xchange-only, is stored in
            available_xchange_pairs = cache.get(ALL_XCHANGE_PAIRS_CACHE_KEY).
        When calculating the price of (currency, to_currency) there are two cases:
        1- (currency, to_currency) is in available_xchange_pairs:
            we calculate the price of (currency, to_currency) directly from cache or db
        2- (currency, to_currency) is NOT in available_xchange_pairs:
            then we must find a proxy_currency such that one of the cases below is true:
            - (currency, proxy_currency) is traded in xchange and (proxy_currency, to_currency) is traded in market
            - (currency, proxy_currency) is traded in xchange and (proxy_currency, to_currency) is traded in xchange
            - (currency, proxy_currency) is traded in market and (proxy_currency, to_currency) is traded in xchange
            otherwise we cannot calculate the price of (currency, to_currency).
            In any of these 3 cases, final_price = price(currency, proxy_currency) * price(proxy_currency, to_currency)
        """
        if currency not in XCHANGE_CURRENCIES and to_currency not in XCHANGE_CURRENCIES:
            raise NotImplementedError
        if currency == to_currency:
            return Decimal(1), Decimal(1)

        available_xchange_pairs = cls._get_all_xchange_pairs()
        if (currency, to_currency) in available_xchange_pairs:
            proxy_currency = to_currency
        else:
            for pair in available_xchange_pairs:
                if pair[0] == currency and (
                    [pair[1], to_currency] in AVAILABLE_MARKETS or (pair[1], to_currency) in available_xchange_pairs
                ):
                    proxy_currency = pair[1]
                    break
            else:
                for pair in AVAILABLE_MARKETS:
                    if pair[0] == currency and (pair[1], to_currency) in available_xchange_pairs:
                        proxy_currency = pair[1]
                        break
                else:
                    return Decimal(0), Decimal(0)
        return cls._get_xchange_price(currency, to_currency, proxy_currency, db_fallback=db_fallback)

    @classmethod
    def _get_all_xchange_pairs(cls) -> List[Tuple[int]]:
        try:
            return cache.get(ALL_XCHANGE_PAIRS_CACHE_KEY, [])
        except RedisError:
            return []

    @classmethod
    def _get_xchange_price(
        cls, currency: int, to_currency: int, proxy_currency: int, *, db_fallback=False
    ) -> Tuple[Decimal, Decimal]:
        if proxy_currency == to_currency:
            return cls._get_price_range_in_xchange(currency=currency, to_currency=to_currency, db_fallback=db_fallback)
        if [currency, proxy_currency] in AVAILABLE_MARKETS:
            currency_proxy_pair_price_buy, currency_proxy_pair_price_sell = MarketPriceEstimator.get_price_range(
                currency=currency, to_currency=proxy_currency, db_fallback=db_fallback
            )
            proxy_to_currency_pair_price_buy, proxy_to_currency_pair_price_sell = cls._get_price_range_in_xchange(
                currency=proxy_currency, to_currency=to_currency, db_fallback=db_fallback
            )
        elif [proxy_currency, to_currency] in AVAILABLE_MARKETS:
            currency_proxy_pair_price_buy, currency_proxy_pair_price_sell = cls._get_price_range_in_xchange(
                currency=currency, to_currency=proxy_currency, db_fallback=db_fallback
            )
            proxy_to_currency_pair_price_buy, proxy_to_currency_pair_price_sell = MarketPriceEstimator.get_price_range(
                currency=proxy_currency, to_currency=to_currency, db_fallback=db_fallback
            )
        else:
            currency_proxy_pair_price_buy, currency_proxy_pair_price_sell = cls._get_price_range_in_xchange(
                currency=currency, to_currency=proxy_currency, db_fallback=db_fallback
            )
            proxy_to_currency_pair_price_buy, proxy_to_currency_pair_price_sell = cls._get_price_range_in_xchange(
                currency=proxy_currency, to_currency=to_currency, db_fallback=db_fallback
            )
        estimate_buy = currency_proxy_pair_price_buy * proxy_to_currency_pair_price_buy
        estimate_sell = currency_proxy_pair_price_sell * proxy_to_currency_pair_price_sell

        symbol = get_market_symbol(currency, to_currency)
        if precision := PRICE_PRECISIONS.get(symbol):
            estimate_buy = Decimal(estimate_buy).quantize(precision)
            estimate_sell = Decimal(estimate_sell).quantize(precision)
        return estimate_buy, estimate_sell

    @classmethod
    def _get_price_range_in_xchange(
        cls, currency: int, to_currency: int = RIAL, *, db_fallback=False
    ) -> Tuple[Decimal, Decimal]:
        try:
            estimate_buy, estimate_sell = cls._get_prices_from_cache(currency, to_currency)
        except RedisError as e:
            if not db_fallback:
                raise e
            estimate_buy, estimate_sell = cls._get_prices_from_db(currency, to_currency)
        return estimate_buy, estimate_sell

    @classmethod
    def _get_prices_from_cache(cls, currency: int, to_currency: int) -> Tuple[Decimal, Decimal]:
        prices = cache.get(XCHANGE_PAIR_PRICES_CACHE_KEY.format(currency=currency, to_currency=to_currency))
        if prices:
            return Decimal(prices.get('buy_price', 0)), Decimal(prices.get('sell_price', 0))
        return Decimal(0), Decimal(0)

    @classmethod
    def _get_prices_from_db(cls, currency: int, to_currency: int) -> Tuple[Decimal, Decimal]:
        market_status = MarketStatus.objects.filter(
            Q(base_currency=currency, quote_currency=to_currency)
            | Q(quote_currency=currency, base_currency=to_currency)
        ).first()
        if not market_status:
            return Decimal(0), Decimal(0)
        if market_status.base_currency == currency:
            return market_status.base_to_quote_price_buy, market_status.base_to_quote_price_sell
        if market_status.quote_currency == currency:
            return market_status.quote_to_base_price_buy, market_status.quote_to_base_price_sell
