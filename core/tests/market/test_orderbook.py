import unittest
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.market.models import Market, Order
from exchange.market.orderbook import OrderBook, OrderBookGenerator
from exchange.matcher.matcher import Matcher, post_processing_matcher_round
from tests.base.utils import create_order


class OrderBookTestBase(APITestCase):
    @staticmethod
    def create_orders_list(src, dst, tp, prices, amounts):
        orders = [
            Order(
                user_id=201 + i % 4,
                src_currency=src,
                dst_currency=dst,
                order_type=tp,
                price=price,
                amount=amount + i * 10,
                matched_amount=i * 10,
                status=Order.STATUS.active,
            )
            for i, (price, amount) in enumerate(zip(prices, amounts))
        ]
        Order.objects.bulk_create(orders)

    @staticmethod
    def get_orders_list(prices, amounts, counts):
        return [
            {'_price': price, '_amount': amount, '_count': count}
            for price, amount, count in zip(prices, amounts, counts)
        ]

    @staticmethod
    def set_market_price(market, price):
        cache.set(f'market_{market.id}_last_price', price)


class OrderBookTest(OrderBookTestBase):

    def test_orderbook_values(self):
        self.create_orders_list(
            Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.sell,
            [817, 817, 818, 820, 821, 821, 830, 840],
            [100, 490, 120, 100, 1000, 10, 3000, 200],
        )
        book = OrderBook('sell', 'BTCUSDT')
        assert book.market.src_currency == Currencies.btc
        assert book.market.dst_currency == Currencies.usdt
        assert book.orders == self.get_orders_list(
            [817, 818, 820, 821, 830, 840],
            [590, 120, 100, 1010, 3000, 200],
            [2, 1, 1, 2, 1, 1],
        )
        assert book.best_price == 817
        assert book.best_active_price == 817
        assert book.last_active_price is None
        assert book.last_skipped_price is None

    def test_orderbook_group_by_expression_by_rows_above_limit(self):
        price = 29990
        amount = 20
        count = OrderBook.MAX_ACTIVE_ORDERS * 2 + 1
        side = Order.ORDER_TYPES.sell
        self.create_orders_list(Currencies.usdt, Currencies.rls, side, [price] * count, [amount] * count)
        book = OrderBook('sell', 'USDTIRT')
        assert book.book_orders == self.get_orders_list([price], [amount * count], [count])

    def test_skip_orderbook_matches(self):
        self.create_orders_list(
            Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.sell,
            [817, 817, 818, 820, 821, 821, 830, 840],
            [100, 490, 120, 100, 1000, 10, 3000, 200],
        )
        self.create_orders_list(
            Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.buy,
            [818, 818, 817, 816, 816, 815, 810, 800],
            [300, 200, 50, 123, 500, 9, 5000, 3000],
        )
        sell_book = OrderBook('sell', 'BTCUSDT')
        buy_book = OrderBook('buy', 'BTCUSDT')
        OrderBookGenerator.skip_order_matches(sell_book, buy_book)
        assert sell_book.orders == self.get_orders_list(
            [817, 818, 820, 821, 830, 840],
            [40, 120, 100, 1010, 3000, 200],
            [2, 1, 1, 2, 1, 1],
        )
        assert buy_book.orders == self.get_orders_list(
            [818, 817, 816, 815, 810, 800],
            [0, 0, 623, 9, 5000, 3000],
            [2, 1, 2, 1, 1, 1],
        )
        assert buy_book.best_price == 818
        assert buy_book.best_active_price == 816
        assert buy_book.last_skipped_price == 817
        assert buy_book.book_orders == self.get_orders_list(
            [816, 815, 810, 800],
            [623, 9, 5000, 3000],
            [2, 1, 1, 1],
        )
        assert sell_book.has_match
        assert buy_book.has_match

    def test_orderbook_skips_on_partial_match(self):
        sell_book = OrderBook('sell', 'BTCUSDT')
        buy_book = OrderBook('buy', 'BTCUSDT')
        sell_book.orders = self.get_orders_list([817, 818, 820], [40, 120, 100], [2, 1, 1])
        buy_book.orders = self.get_orders_list([817, 815, 810], [30, 70, 600], [2, 1, 2])
        OrderBookGenerator.skip_order_matches(sell_book, buy_book)
        assert sell_book.has_match
        assert buy_book.has_match

    def test_orderbook_skips_on_no_match(self):
        sell_book = OrderBook('sell', 'BTCUSDT')
        buy_book = OrderBook('buy', 'BTCUSDT')
        sell_book.orders = self.get_orders_list([817, 818, 820], [40, 120, 100], [2, 1, 1])
        buy_book.orders = self.get_orders_list([816, 815, 810], [30, 70, 600], [2, 1, 2])
        OrderBookGenerator.skip_order_matches(sell_book, buy_book)
        assert not sell_book.has_match
        assert not buy_book.has_match

    def test_orderbook(self):
        self.create_orders_list(
            Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.sell,
            [816, 817, 818, 820, 821, 821, 830],
            [100, 290, 120, 100, 1000, 10, 3000],
        )
        self.create_orders_list(
            Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.buy,
            [818, 818, 817, 816, 816, 815, 810],
            [300, 200, 50, 123, 500, 9, 5000],
        )
        market = Market.by_symbol('BTCUSDT')
        self.set_market_price(market, 817)
        OrderBookGenerator.create_market_orderbooks(market)
        assert cache.get('orderbook_BTCUSDT_bids') == '[["818","10"],["820","100"],["821","1010"],["830","3000"]]'
        assert cache.get('orderbook_BTCUSDT_asks') == '[["817","50"],["816","623"],["815","9"],["810","5000"]]'
        assert cache.get('orderbook_BTCUSDT_best_sell') == 816
        assert cache.get('orderbook_BTCUSDT_best_buy') == 818
        assert cache.get('orderbook_BTCUSDT_best_active_sell') == 818
        assert cache.get('orderbook_BTCUSDT_best_active_buy') == 817
        assert cache.get('orderbook_BTCUSDT_last_trade_price') == '817'
        assert cache.get('orderbook_BTCUSDT_skips')

        response = self.client.get('/v2/orderbook/BTCUSDT')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)
        assert data['status'] == 'ok'
        assert data['lastUpdate'] == int(cache.get('orderbook_BTCUSDT_update_time'))
        assert data['lastTradePrice'] == '817'
        assert data['asks'] == [['817', '50'], ['816', '623'], ['815', '9'], ['810', '5000']]
        assert data['bids'] == [['818', '10'], ['820', '100'], ['821', '1010'], ['830', '3000']]

    def test_orderbook_get_empty_after_nonempty(self):
        self.create_orders_list(Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.sell, [818], [100])
        self.create_orders_list(Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.buy, [816], [300])
        market = Market.by_symbol('BTCUSDT')
        OrderBookGenerator.create_market_orderbooks(market)
        assert cache.get('orderbook_BTCUSDT_bids') == '[["818","100"]]'
        assert cache.get('orderbook_BTCUSDT_asks') == '[["816","300"]]'
        Order.objects.update(status=Order.STATUS.canceled)
        OrderBookGenerator.create_market_orderbooks(market)
        assert cache.get('orderbook_BTCUSDT_bids') == '[]'
        assert cache.get('orderbook_BTCUSDT_asks') == '[]'

    def test_orderbook_stop_loss_inactive_orders(self):
        self.create_orders_list(
            Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.sell,
            [816, 817, 818, 820],
            [100, 290, 120, 100],
        )
        self.create_orders_list(
            Currencies.btc, Currencies.usdt, Order.ORDER_TYPES.buy,
            [818, 818, 817, 816, 816],
            [300, 200, 50, 123, 500],
        )
        market = Market.by_symbol('BTCUSDT')
        OrderBookGenerator.create_market_orderbooks(market)
        bids_before_stop_loss = cache.get('orderbook_BTCUSDT_bids')
        asks_before_stop_loss = cache.get('orderbook_BTCUSDT_asks')

        users = User.objects.all()
        create_order(users[0], Currencies.btc, Currencies.usdt, 100, 815, sell=True, stop=814)
        create_order(users[1], Currencies.btc, Currencies.usdt, 100, 821, sell=False, stop=822)
        create_order(users[2], Currencies.btc, Currencies.usdt, 100, 815, sell=True, market=True, stop=815)
        create_order(users[3], Currencies.btc, Currencies.usdt, 100, 821, sell=False, market=True, stop=821)

        OrderBookGenerator.create_market_orderbooks(market)
        assert cache.get('orderbook_BTCUSDT_bids') == bids_before_stop_loss
        assert cache.get('orderbook_BTCUSDT_asks') == asks_before_stop_loss

    @override_settings(ENABLE_STOP_ORDERS=True)
    def test_orderbook_stop_loss_active_orders(self):
        market = Market.by_symbol('BTCUSDT')
        users = User.objects.all()
        create_order(users[0], Currencies.btc, Currencies.usdt, 40, 815, sell=True, stop=814)
        create_order(users[1], Currencies.btc, Currencies.usdt, 100, 821, sell=False, stop=822)
        create_order(users[2], Currencies.btc, Currencies.usdt, 120, 815, sell=True, market=True, stop=815)
        create_order(users[3], Currencies.btc, Currencies.usdt, 70, 821, sell=False, market=True, stop=821)
        OrderBookGenerator.create_market_orderbooks(market)
        assert cache.get('orderbook_BTCUSDT_bids') == '[]'
        assert cache.get('orderbook_BTCUSDT_asks') == '[]'

        matcher = Matcher(market)
        matcher.update_last_price(814)
        post_processing_matcher_round(market, matcher.LAST_PRICE_RANGE)
        OrderBookGenerator.create_market_orderbooks(market)
        assert cache.get('orderbook_BTCUSDT_bids') == '[["815","40"]]'
        assert cache.get('orderbook_BTCUSDT_asks') == '[]'

        matcher = Matcher(market)
        matcher.update_last_price(822)
        post_processing_matcher_round(market, matcher.LAST_PRICE_RANGE)
        OrderBookGenerator.create_market_orderbooks(market)
        assert cache.get('orderbook_BTCUSDT_bids') == '[]'
        assert cache.get('orderbook_BTCUSDT_asks') == '[["821","60"]]'

    def test_full_orderbook_all(self):
        self.create_orders_list(
            Currencies.btc,
            Currencies.usdt,
            Order.ORDER_TYPES.sell,
            [816, 817, 818, 820, 821, 821, 830],
            [100, 290, 120, 100, 1000, 10, 3000],
        )
        self.create_orders_list(
            Currencies.btc,
            Currencies.usdt,
            Order.ORDER_TYPES.buy,
            [818, 818, 817, 816, 816, 815, 810],
            [300, 200, 50, 123, 500, 9, 5000],
        )
        market1 = Market.by_symbol('BTCUSDT')
        self.set_market_price(market1, 817)

        self.create_orders_list(
            Currencies.btc,
            Currencies.rls,
            Order.ORDER_TYPES.sell,
            [11560000000, 11570000000],
            [0.01, 0.007],
        )
        self.create_orders_list(
            Currencies.btc,
            Currencies.rls,
            Order.ORDER_TYPES.buy,
            [11530000000, 11520000000],
            [0.006, 0.013],
        )
        market2 = Market.by_symbol('BTCIRT')
        results = [OrderBookGenerator.create_market_orderbooks(market) for market in [market1, market2]]

        response = self.client.get('/v2/orderbook/all')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)
        assert data['status'] == 'ok'
        data.pop('status')
        assert len(data) == len(Market.objects.all())
        assert 'BTCUSDT' in data
        assert data['BTCUSDT']['lastUpdate'] == int(cache.get('orderbook_BTCUSDT_update_time'))
        assert data['BTCUSDT']['lastTradePrice'] == '817'
        assert data['BTCUSDT']['asks'] == [['817', '50'], ['816', '623'], ['815', '9'], ['810', '5000']]
        assert data['BTCUSDT']['bids'] == [['818', '10'], ['820', '100'], ['821', '1010'], ['830', '3000']]
        assert data['BTCIRT']['lastTradePrice'] == ''

    def test_empty_orderbook_all(self):
        market = Market.by_symbol('BTCUSDT')
        result = OrderBookGenerator.create_market_orderbooks(market)

        response = self.client.get('/v2/orderbook/all')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert 'BTCUSDT' in data
        assert data['BTCUSDT']['lastUpdate'] == int(cache.get('orderbook_BTCUSDT_update_time'))
        assert data['BTCUSDT']['lastTradePrice'] == ''
        assert data['BTCUSDT']['asks'] == []
        assert data['BTCUSDT']['bids'] == []


class OrderBookV3Test(OrderBookTestBase):
    def test_orderbook(self):
        self.create_orders_list(
            Currencies.btc,
            Currencies.usdt,
            Order.ORDER_TYPES.sell,
            [816, 817, 818, 820, 821, 821, 830],
            [100, 290, 120, 100, 1000, 10, 3000],
        )
        self.create_orders_list(
            Currencies.btc,
            Currencies.usdt,
            Order.ORDER_TYPES.buy,
            [818, 818, 817, 816, 816, 815, 810],
            [300, 200, 50, 123, 500, 9, 5000],
        )
        market = Market.by_symbol('BTCUSDT')
        self.set_market_price(market, 817)
        OrderBookGenerator.create_market_orderbooks(market)
        assert cache.get('orderbook_BTCUSDT_bids') == '[["818","10"],["820","100"],["821","1010"],["830","3000"]]'
        assert cache.get('orderbook_BTCUSDT_asks') == '[["817","50"],["816","623"],["815","9"],["810","5000"]]'
        assert cache.get('orderbook_BTCUSDT_best_sell') == 816
        assert cache.get('orderbook_BTCUSDT_best_buy') == 818
        assert cache.get('orderbook_BTCUSDT_best_active_sell') == 818
        assert cache.get('orderbook_BTCUSDT_best_active_buy') == 817
        assert cache.get('orderbook_BTCUSDT_last_trade_price') == '817'
        assert cache.get('orderbook_BTCUSDT_skips')

        response = self.client.get('/v3/orderbook/BTCUSDT')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)
        assert data['status'] == 'ok'
        assert data['lastUpdate'] == int(cache.get('orderbook_BTCUSDT_update_time'))
        assert data['lastTradePrice'] == '817'
        assert data['bids'] == [['817', '50'], ['816', '623'], ['815', '9'], ['810', '5000']]
        assert data['asks'] == [['818', '10'], ['820', '100'], ['821', '1010'], ['830', '3000']]

    def test_full_orderbook_all(self):
        self.create_orders_list(
            Currencies.btc,
            Currencies.usdt,
            Order.ORDER_TYPES.sell,
            [816, 817, 818, 820, 821, 821, 830],
            [100, 290, 120, 100, 1000, 10, 3000],
        )
        self.create_orders_list(
            Currencies.btc,
            Currencies.usdt,
            Order.ORDER_TYPES.buy,
            [818, 818, 817, 816, 816, 815, 810],
            [300, 200, 50, 123, 500, 9, 5000],
        )
        market1 = Market.by_symbol('BTCUSDT')
        self.set_market_price(market1, 817)

        self.create_orders_list(
            Currencies.btc,
            Currencies.rls,
            Order.ORDER_TYPES.sell,
            [11560000000, 11570000000],
            [0.01, 0.007],
        )
        self.create_orders_list(
            Currencies.btc,
            Currencies.rls,
            Order.ORDER_TYPES.buy,
            [11530000000, 11520000000],
            [0.006, 0.013],
        )
        market2 = Market.by_symbol('BTCIRT')
        results = [OrderBookGenerator.create_market_orderbooks(market) for market in [market1, market2]]

        response = self.client.get('/v3/orderbook/all')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)
        assert data['status'] == 'ok'
        data.pop('status')
        assert len(data) == len(Market.objects.all())
        assert 'BTCUSDT' in data
        assert data['BTCUSDT']['lastUpdate'] == int(cache.get('orderbook_BTCUSDT_update_time'))
        assert data['BTCUSDT']['lastTradePrice'] == '817'
        assert data['BTCUSDT']['bids'] == [['817', '50'], ['816', '623'], ['815', '9'], ['810', '5000']]
        assert data['BTCUSDT']['asks'] == [['818', '10'], ['820', '100'], ['821', '1010'], ['830', '3000']]
        assert data['BTCIRT']['lastTradePrice'] == ''


class TestOrderBookGenerator(unittest.TestCase):
    def setUp(self):
        cache.clear()
        self.symbol = 'BTCUSDT'
        self.side = 'bids'
        self.tp = 'sell'
        self.market = MagicMock()
        self.market.symbol = self.symbol
        self.book = MagicMock()
        self.book.tp = self.tp
        self.book.market = self.market
        self.book.public_book_orders = [['50000', '1']]
        self.book.best_price = '50000'
        self.book.best_active_price = '50000'
        self.book.last_active_price = '50000'

        OrderBookGenerator.all_orderbooks = {
            self.symbol: {
                self.side: self.book.public_book_orders,
                f'_{self.side}__UpdateTime': 1000000,  # Initial timestamp in milliseconds
            },
        }
        OrderBookGenerator.CACHE_TIMEOUT = 60
        self.cache_expiration_duration_ms = (OrderBookGenerator.CACHE_TIMEOUT - 10) * 1000
        OrderBookGenerator._cache_values.clear()

    @patch('exchange.market.orderbook.time.time')
    def test_cache_book_not_updated_if_data_unchanged_and_cache_not_expired(self, mock_time):
        cache_key = f'orderbook_{self.symbol}_{self.side}'
        mock_time.return_value = 1000040
        prev_book = OrderBookGenerator.all_orderbooks[self.symbol]
        OrderBookGenerator.cache_update_times[cache_key] = 1000000
        OrderBookGenerator.cache_orderbook_values(self.book, prev_book)
        assert cache_key not in OrderBookGenerator._cache_values

    @patch('exchange.market.orderbook.time.time')
    def test_cache_book_updated_if_data_unchanged_and_cache_expired(self, mock_time):
        cache_key = f'orderbook_{self.symbol}_{self.side}'
        mock_time.return_value = 1000060
        prev_book = OrderBookGenerator.all_orderbooks[self.symbol]
        OrderBookGenerator.cache_update_times[cache_key] = 1000000
        OrderBookGenerator.cache_orderbook_values(self.book, prev_book)
        assert cache_key in OrderBookGenerator._cache_values

    @patch('exchange.market.orderbook.time.time')
    def test_cache_book_updated_if_data_changed(self, mock_time):
        cache_key = f'orderbook_{self.symbol}_{self.side}'
        mock_time.return_value = 1000040
        prev_book = OrderBookGenerator.all_orderbooks[self.symbol]
        OrderBookGenerator.cache_update_times[cache_key] = 1000000
        self.book.public_book_orders = [['50001', '1']]
        OrderBookGenerator.cache_orderbook_values(self.book, prev_book)
        assert cache_key in OrderBookGenerator._cache_values

    @patch('exchange.market.orderbook.time.time')
    def test_cache_market_values_not_updated_if_data_unchanged_and_cache_not_expired(self, mock_time):
        cache_key = f'orderbook_{self.symbol}_last_trade_price'
        mock_time.return_value = 1000040
        prev_book = {'lastTradePrice': '50000'}
        OrderBookGenerator.cache_update_times[cache_key] = 1000000
        OrderBookGenerator.cache_market_values(self.symbol, 0, self.book.last_active_price, '50000', prev_book)
        assert cache_key not in OrderBookGenerator._cache_values

    @patch('exchange.market.orderbook.time.time')
    def test_cache_market_values_updated_if_data_unchanged_and_cache_expired(self, mock_time):
        cache_key = f'orderbook_{self.symbol}_last_trade_price'
        mock_time.return_value = 1000060
        prev_book = {'lastTradePrice': '50000'}
        OrderBookGenerator.cache_update_times[cache_key] = 1000000
        OrderBookGenerator.cache_market_values(self.symbol, 0, self.book.last_active_price, '50000', prev_book)
        assert cache_key in OrderBookGenerator._cache_values

    @patch('exchange.market.orderbook.time.time')
    def test_cache_market_values_updated_if_data_changed(self, mock_time):
        cache_key = f'orderbook_{self.symbol}_last_trade_price'
        mock_time.return_value = 1000040
        prev_book = {'lastTradePrice': '50001'}
        OrderBookGenerator.cache_update_times[cache_key] = 1000000
        OrderBookGenerator.cache_market_values(self.symbol, 0, self.book.last_active_price, '50000', prev_book)
        assert cache_key in OrderBookGenerator._cache_values
