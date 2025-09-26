import json
import warnings
from decimal import Decimal

import requests
from django.core.cache import cache
from django.db.models import F, Max, Min, Sum, Window
from django.db.models.functions import FirstValue
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django_ratelimit.decorators import ratelimit
from rest_framework import status

from exchange.base.api import ParseError, PublicAPIView
from exchange.base.calendar import ir_now
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.logging import metric_incr, report_exception
from exchange.base.models import (
    ACTIVE_CRYPTO_CURRENCIES,
    AVAILABLE_MARKETS,
    CURRENCY_CODENAMES,
    VALID_MARKET_SYMBOLS,
    Currencies,
    parse_market_symbol,
)
from exchange.base.parsers import parse_int
from exchange.base.serializers import serialize_timestamp
from exchange.config.config.derived_data.coinmarketcap_ucids import COINMARKETCAP_UCIDS
from exchange.market.models import Market, MarketCandle, OrderMatching
from exchange.market.orderbook import OrderBook, OrderBookGenerator
from exchange.settings import NOBITEX_OPTIONS
from exchange.wallet.withdraw_method import AutomaticWithdrawMethod


class CoinMarketCap:
    UNIFIED_CRYPTO_ASSET_ID = COINMARKETCAP_UCIDS
    CUSTOM_SYMBOLS = {'RLS': 'IRR', 'PMN': 'PMNT', 'IOTA': 'MIOTA', '100K_FLOKI': 'FLOKI',
                      '1B_BABYDOGE': 'BABYDOGE', '1M_NFT': 'NFT', '1M_BTT': 'BTT'}
    REV_CUSTOM_SYMBOLS = {v: k for k, v in CUSTOM_SYMBOLS.items()}
    # TODO: consider amount rates for 1000shib, etc.

    @classmethod
    def get_currency_id(cls, currency):
        if currency not in cls.UNIFIED_CRYPTO_ASSET_ID:
            cls.update_unified_cryptoasset_ids()
        return cls.UNIFIED_CRYPTO_ASSET_ID.get(currency, 0)

    @classmethod
    def get_currency_symbol(cls, currency):
        symbol = CURRENCY_CODENAMES[currency].upper()
        return symbol if symbol not in cls.CUSTOM_SYMBOLS else cls.CUSTOM_SYMBOLS[symbol]

    @classmethod
    def parse_currency_symbol(cls, symbol):
        symbol = symbol if symbol not in cls.REV_CUSTOM_SYMBOLS else cls.REV_CUSTOM_SYMBOLS[symbol]
        try:
            return getattr(Currencies, symbol.lower())
        except AttributeError:
            raise ParseError(f'Invalid asset {symbol}')

    @staticmethod
    def get_market_symbol(base_currency, quote_currency):
        return f'{base_currency}-{quote_currency}'

    @classmethod
    def feed_all_symbol(cls):
        result = [{}]
    @classmethod
    def parse_market_symbol(cls, market_pair):
        if not isinstance(market_pair, str) or market_pair.count('-') != 1:
            raise ParseError('Invalid market pair')
        base, quote = market_pair.split('-')
        return cls.parse_currency_symbol(base), cls.parse_currency_symbol(quote)

    @classmethod
    def update_unified_cryptoasset_ids(cls):
        """
        This method updates crypto asset ids by calling Coinmarketcap API.
        Sample response:
        {
            "data": [
                {
                    "id": 1,
                    "rank": 1,
                    "name": "Bitcoin",
                    "symbol": "BTC",
                    "slug": "bitcoin",
                    "is_active": 1,
                    "first_historical_data": "2013-04-28T18:47:21.000Z",
                    "last_historical_data": "2020-05-05T20:44:01.000Z",
                    "platform": null
                },
                {
                    "id": 825,
                    "rank": 5,
                    "name": "Tether",
                    "symbol": "USDT",
                    "slug": "tether",
                    "is_active": 1,
                    "first_historical_data": "2015-02-25T13:34:26.000Z",
                    "last_historical_data": "2020-05-05T20:44:01.000Z",
                    "platform": {
                        "id": 1027,
                        "name": "Ethereum",
                        "symbol": "ETH",
                        "slug": "ethereum",
                        "token_address": "0xdac17f958d2ee523a2206206994597c13d831ec7"
                    }
                }
            ],
            "status": {
                "timestamp": "2018-06-02T22:51:28.209Z",
                "error_code": 0,
                "error_message": "",
                "elapsed": 10,
                "credit_count": 1
            }
        }

        """
        symbols = (
            cls.get_currency_symbol(currency) for currency in ACTIVE_CRYPTO_CURRENCIES
            if currency not in cls.UNIFIED_CRYPTO_ASSET_ID
        )
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/map'
        api_key = 'a000df5e-6a86-4101-b9bb-3032ac366448'
        r = None
        try:
            r = requests.get(url, params={'CMC_PRO_API_KEY': api_key, 'symbol': ','.join(symbols)}, timeout=2)
            r.raise_for_status()
            cls.warn_missing_asset_ids(r.json()['data'])
            cls.UNIFIED_CRYPTO_ASSET_ID.update({
                cls.parse_currency_symbol(currency_data['symbol']): currency_data['id']
                for currency_data in r.json()['data']
            })
        except:
            if r is not None:
                warnings.warn(f'Coinmarketcap error:\n{r.url}\n{r.json()}')

                excluded_from_sentry_error_codes = {status.HTTP_429_TOO_MANY_REQUESTS}
                if r.status_code in excluded_from_sentry_error_codes:
                    metric_incr('metric_coinmarketcap_map_api_error_codes', labels=(r.status_code,))
                    return

            report_exception()

    @staticmethod
    def warn_missing_asset_ids(data):
        missing_ids = {c["symbol"].lower(): c["id"] for c in data}
        message = 'Coinmarketcap missing asset ids:\n'
        message += '\n'.join(f'Currencies.{k}: {v},' for k, v in missing_ids.items())
        warnings.warn(message)


@method_decorator(ratelimit(key='ip', rate='10/1m'), name='get')
@method_decorator(cache_page(60, key_prefix='coinmarketcap'), name='get')
class MarketSummaryView(PublicAPIView):
    """ GET /coinmarketcap/v1/summary """

    def get(self, request):
        data = []
        orderbook_data = self.get_orderbook_data()
        market_data = self.get_market_data()
        for src_currency, dst_currency in AVAILABLE_MARKETS:
            base_currency = CoinMarketCap.get_currency_symbol(src_currency)
            quote_currency = CoinMarketCap.get_currency_symbol(dst_currency)
            orderbook_values = orderbook_data.get((src_currency, dst_currency), {})
            market_values = market_data.get((src_currency, dst_currency), {})
            data.append({
                'trading_pairs': CoinMarketCap.get_market_symbol(base_currency, quote_currency),
                'base_currency': base_currency,
                'quote_currency': quote_currency,
                'last_price': orderbook_values.get('last_price') or Decimal(0),
                'lowest_ask': orderbook_values.get('lowest_ask') or Decimal(0),
                'highest_bid': orderbook_values.get('highest_bid') or Decimal(0),
                'base_volume': market_values.get('base_volume') or Decimal(0),
                'quote_volume': market_values.get('quote_volume') or Decimal(0),
                'price_change_percent_24h': market_values.get('price_change_percent_24h') or Decimal(0),
                'highest_price_24h': market_values.get('highest_price_24h') or Decimal(0),
                'lowest_price_24h': market_values.get('lowest_price_24h') or Decimal(0),
            })
        return self.response(data)

    @staticmethod
    def get_market_data():
        last_24h = ir_now() - timezone.timedelta(days=1)

        market_data = MarketCandle.objects.filter(
            resolution=MarketCandle.RESOLUTIONS.minute,
            start_time__gte=last_24h,
        ).values('market').annotate(
            src_currency=F('market__src_currency'),
            dst_currency=F('market__dst_currency'),
            base_volume=Window(Sum('trade_amount'), partition_by=('market',)),
            quote_volume=Window(Sum('trade_total'), partition_by=('market',)),
            open_price_24h=Window(FirstValue('open_price'), order_by=('start_time',), partition_by=('market',)),
            close_price_24h=Window(FirstValue('close_price'), order_by=F('start_time').desc(), partition_by=('market',)),
            highest_price_24h=Window(Max('high_price'), partition_by=('market',)),
            lowest_price_24h=Window(Min('low_price'), partition_by=('market',)),
        ).distinct()

        return {
            (row['src_currency'], row['dst_currency']): {
                'base_volume': row['base_volume'],
                'quote_volume': row['quote_volume'],
                'price_change_percent_24h': (
                    (row['close_price_24h'] / row['open_price_24h'] - 1) * 100
                ).quantize(Decimal('0E-2')) if row['open_price_24h'] else None,
                'highest_price_24h': row['highest_price_24h'],
                'lowest_price_24h': row['lowest_price_24h'],
            } for row in market_data
        }

    def get_orderbook_data(self):
        last_trade_prices = self.get_last_trade_prices()
        bids = self.get_bids()
        asks = self.get_asks()

        orderbook_data = {}
        for symbol in VALID_MARKET_SYMBOLS:
            trade_price = last_trade_prices.get(f'orderbook_{symbol}_last_trade_price', '')
            bid = json.loads(bids.get(f'orderbook_{symbol}_bids', '[]'))
            lowest_ask = bid[0][0] if bid else None
            ask = json.loads(asks.get(f'orderbook_{symbol}_asks', '[]'))
            highest_bid = ask[0][0] if ask else None

            orderbook_data[parse_market_symbol(symbol)] = {
                'last_price': trade_price,
                'lowest_ask': lowest_ask,
                'highest_bid': highest_bid,
            }
        return orderbook_data

    @staticmethod
    def get_last_trade_prices():
        trade_price_keys = [f'orderbook_{symbol}_last_trade_price' for symbol in VALID_MARKET_SYMBOLS]
        return cache.get_many(trade_price_keys)

    def get_bids(self):
        return self._get_orderbooks_items('bid')

    def get_asks(self):
        return self._get_orderbooks_items('ask')

    @staticmethod
    def _get_orderbooks_items(tp):
        keys = [f'orderbook_{symbol}_{tp}s' for symbol in VALID_MARKET_SYMBOLS]
        return cache.get_many(keys)


@method_decorator(ratelimit(key='ip', rate='10/1m'), name='get')
@method_decorator(cache_page(60, key_prefix='coinmarketcap'), name='get')
class MarketAssetsView(PublicAPIView):
    """ GET /coinmarketcap/v1/assets """

    def get(self, request):
        data = {}
        for currency in ACTIVE_CRYPTO_CURRENCIES:
            networks = CURRENCY_INFO[currency]['network_list'].values()
            networks_keys = CURRENCY_INFO[currency]['network_list'].keys()
            min_network_withdraw = min(
                (
                    AutomaticWithdrawMethod.get_withdraw_min(currency, network)
                    for network in networks_keys
                    if CURRENCY_INFO[currency]['network_list'][network].get('withdraw_enable', True)
                ),
                default=Decimal(0),
            )
            max_network_withdraw = sum(
                (
                    AutomaticWithdrawMethod.get_withdraw_max(currency, network)
                    for network in networks_keys
                    if CURRENCY_INFO[currency]['network_list'][network].get('withdraw_enable', True)
                ),
                start=Decimal(0),
            )
            symbol = CoinMarketCap.get_currency_symbol(currency)
            data[symbol] = {
                'name': Currencies[currency],
                'unified_cryptoasset_id': CoinMarketCap.get_currency_id(currency),
                'can_withdraw': any(network.get('withdraw_enable', True) for network in networks),
                'can_deposit': any(network.get('deposit_enable', True) for network in networks),
                'min_withdraw': max(NOBITEX_OPTIONS['minWithdraws'][currency], min_network_withdraw),
                'max_withdraw': min(NOBITEX_OPTIONS['maxWithdraws'][currency], max_network_withdraw),
                'maker_fee': NOBITEX_OPTIONS['tradingFees']['makerFees'][0],
                'taker_fee': NOBITEX_OPTIONS['tradingFees']['takerFees'][0],
            }
        return self.response(data)


@method_decorator(ratelimit(key='ip', rate='10/1m'), name='get')
@method_decorator(cache_page(60, key_prefix='coinmarketcap'), name='get')
class MarketTickerView(PublicAPIView):
    """ GET /coinmarketcap/v1/ticker """

    def get(self, request):
        data = {}
        orderbook_data = self.get_orderbook_data()
        market_data = self.get_market_data()
        market_states = self.get_market_states()
        for src_currency, dst_currency in AVAILABLE_MARKETS:
            base_currency = CoinMarketCap.get_currency_symbol(src_currency)
            quote_currency = CoinMarketCap.get_currency_symbol(dst_currency)
            orderbook_values = orderbook_data.get((src_currency, dst_currency), {})
            market_values = market_data.get((src_currency, dst_currency), {})
            market_state = market_states.get((src_currency, dst_currency), {})
            market_pair = CoinMarketCap.get_market_symbol(base_currency, quote_currency)
            data[market_pair] = ({
                'base_id': CoinMarketCap.get_currency_id(src_currency),
                'quote_id': CoinMarketCap.get_currency_id(dst_currency),
                'last_price': orderbook_values.get('last_price') or Decimal(0),
                'base_volume': market_values.get('base_volume') or Decimal(0),
                'quote_volume': market_values.get('quote_volume') or Decimal(0),
                'isFrozen': int(market_state.get('is_frozen', True)),
            })
        return self.response(data)

    @staticmethod
    def get_market_data():
        last_24h = ir_now() - timezone.timedelta(days=1)
        market_data = MarketCandle.objects.filter(
            resolution=MarketCandle.RESOLUTIONS.minute,
            start_time__gte=last_24h,
        ).values('market').annotate(
            src_currency=F('market__src_currency'),
            dst_currency=F('market__dst_currency'),
            base_volume=Sum('trade_amount'),
            quote_volume=Sum('trade_total'),
        )

        return {
            (row['src_currency'], row['dst_currency']): {
                'base_volume': row['base_volume'],
                'quote_volume': row['quote_volume'],
            } for row in market_data
        }

    def get_orderbook_data(self):
        last_trade_prices = self.get_last_trade_prices()
        return {
            parse_market_symbol(symbol.replace('orderbook_', '').replace('_last_trade_price', '')): {
                'last_price': last_trade_price,
            }
            for symbol, last_trade_price in last_trade_prices.items()
        }

    @staticmethod
    def get_last_trade_prices():
        trade_price_keys = [f'orderbook_{symbol}_last_trade_price' for symbol in VALID_MARKET_SYMBOLS]
        return cache.get_many(trade_price_keys)

    @staticmethod
    def get_market_states():
        active_markets = Market.objects.filter(src_currency__in=ACTIVE_CRYPTO_CURRENCIES).values()
        return {
            (row['src_currency'], row['dst_currency']): {'is_frozen': not row['is_active']} for row in active_markets
        }


@method_decorator(ratelimit(key='ip', rate=f'{len(AVAILABLE_MARKETS) * 10}/1m'), name='get')
@method_decorator(cache_page(60, key_prefix='coinmarketcap'), name='get')
class OrderBookView(PublicAPIView):
    """ GET /coinmarketcap/v1/orderbook/market_pair """

    def get(self, request, market_pair):
        depth = self.parse_depth(default=1000)
        level = self.parse_level(default=2)
        src_currency, dst_currency = CoinMarketCap.parse_market_symbol(market_pair)
        market = Market.get_for(src_currency, dst_currency)
        book_items = 1 if level == 1 else depth // 2
        if 0 < book_items < OrderBook.MAX_BOOK_ITEMS:
            data = self.get_orderbook_from_cache(market, book_items)
        else:
            data = self.calculate_orderbook(market, book_items)
        return self.response(data)

    def parse_depth(self, default):
        depth = parse_int(self.g('depth')) or 0
        if depth not in (0, 5, 10, 20, 50, 100, 500):
            raise ParseError('Unexpected depth')
        return depth or default

    def parse_level(self, default):
        level = parse_int(self.g('level', default))
        if level not in (1, 2, 3):
            raise ParseError('Unexpected level')
        return level

    @staticmethod
    def calculate_orderbook(market, book_items):
        update_time = timezone.now()
        sell_book = OrderBook('sell', market, update_time)
        buy_book = OrderBook('buy', market, update_time)
        sell_book.MAX_BOOK_ITEMS = book_items
        buy_book.MAX_BOOK_ITEMS = book_items
        sell_book.MAX_ACTIVE_ORDERS = book_items * 3
        buy_book.MAX_ACTIVE_ORDERS = book_items * 3
        OrderBookGenerator.skip_order_matches(sell_book, buy_book)
        return {
            'timestamp': serialize_timestamp(update_time),
            'asks': sell_book.public_book_orders,
            'bids': buy_book.public_book_orders,
        }

    @staticmethod
    def get_orderbook_from_cache(market, book_items):
        asks = json.loads(cache.get(f'orderbook_{market.symbol}_bids', '[]'))
        bids = json.loads(cache.get(f'orderbook_{market.symbol}_asks', '[]'))
        timestamp = json.loads(cache.get(f'orderbook_{market.symbol}_update_time', '0'))
        return {
            'timestamp': timestamp,
            'asks': asks[:book_items],
            'bids': bids[:book_items],
        }


@method_decorator(ratelimit(key='ip', rate=f'{len(AVAILABLE_MARKETS) * 10}/1m'), name='get')
@method_decorator(cache_page(60, key_prefix='coinmarketcap'), name='get')
class TradesView(PublicAPIView):
    """ GET /coinmarketcap/v1/trades/market_pair """

    def get(self, request, market_pair):
        src_currency, dst_currency = CoinMarketCap.parse_market_symbol(market_pair)
        market = Market.get_for(src_currency, dst_currency)
        recent = timezone.now() - timezone.timedelta(hours=1)
        trades = OrderMatching.get_trades(market=market, date_from=recent).order_by('-pk')[:10000]
        data = [{
            'trade_id': trade.id,
            'price': trade.matched_price,
            'base_volume': trade.matched_amount,
            'quote_volume': trade.matched_total_price,
            'timestamp': serialize_timestamp(trade.created_at),
            'type': 'Buy' if trade.is_seller_maker else 'Sell',
        } for trade in trades]
        return self.response(data)


@method_decorator(ratelimit(key='ip', rate='10/1m'), name='get')
@method_decorator(cache_page(60, key_prefix='coinmarketcap'), name='get')
class MarketIdsView(PublicAPIView):
    """ GET /coinmarketcap/v1/ids """

    def get(self, request):
        data = {}
        for currency in ACTIVE_CRYPTO_CURRENCIES:
            symbol = CoinMarketCap.get_currency_symbol(currency)
            data[symbol] = {
                'id': currency,
                'name': Currencies[currency],
                'symbol': CURRENCY_CODENAMES[currency],
                'coinmarketcap_id': CoinMarketCap.get_currency_id(currency),
                'coinmarketcap_symbol': symbol,
            }
        return self.response(data)
