import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.base.models import Settings as NobitexSettings
from exchange.market.models import Market, OrderMatching
from exchange.market.orderbook import OrderBookGenerator
from exchange.matcher.matcher import Matcher, post_processing_matcher_round
from tests.base.utils import create_order
from tests.matcher.matcher_flaw_helpers import (
    _create_orders_after_first_order_book_run,
    _create_orders_before_first_order_book_run,
)


@pytest.mark.matcher
class TestMatcherFlaws(TestCase):
    @staticmethod
    def create_order(
        user_id: int,
        market: Market,
        amount,
        price,
        order_type,
        time,
        is_market=False,
    ):
        user = User.objects.get(pk=user_id)
        order = create_order(
            user,
            market.src_currency,
            market.dst_currency,
            amount,
            price,
            sell=order_type == 'sell',
            market=is_market,
        )
        order.created_at = timezone.datetime.fromisoformat(time)
        order.save(update_fields=('created_at',))
        return order

    def setUp(self):
        Matcher.MARKET_LAST_PROCESSED_TIME.clear()
        Matcher._get_symbols_that_use_runtime_limit_logic.clear()
        cache.clear()
        NobitexSettings.set_dict(Matcher.ORDERBOOK_RUNTIME_LIMITATION_MARKETS_SETTINGS_KEY, ['BTCIRT'])

    @patch.dict(settings.NOBITEX_OPTIONS['minOrders'], {Currencies.rls: Decimal('20')})
    def test_missed_matching_shadow(self):
        market = Market.by_symbol('BTCIRT')
        # Sample Orderbook
        self.create_order(201, market, '130', '40_500_0', 'sell', '2023-01-27 08:57:14.437232+03:30')
        self.create_order(202, market, '85', '41_200_0', 'sell', '2023-01-27 09:01:54.119302+03:30')
        self.create_order(203, market, '151', '39_800_0', 'buy', '2023-01-27 09:05:28.376781+03:30')
        last_order = self.create_order(204, market, '63', '39_550_0', 'buy', '2023-01-27 09:05:31.787554+03:30')
        Matcher(market).do_matching_round()
        assert not OrderMatching.objects.exists()
        assert Matcher.MARKET_LAST_PROCESSED_TIME[market.id] == last_order.created_at
        assert Matcher.MARKET_LAST_BEST_PRICES.get(market.id) == (Decimal('405000'), Decimal('398000'))

        # Missed matching happens when last order is not active anymore,
        # or when it's first on orderbook and gets matched at the start of next round
        last_order.do_cancel()

        self.create_order(
            203,
            market,
            '0.00419',
            '41_000_0',
            'sell',
            '2023-01-27 09:05:32.687125+03:30',
            is_market=True,
        )
        # This order got stuck in view and was committed late
        self.create_order(202, market, '196', '45_019_0', 'buy', '2023-01-27 09:05:31.371241+03:30')

        Matcher(market).do_matching_round()
        # check shadow
        assert not OrderMatching.objects.filter(matched_price=45_019_0).exists()

    def test_orderBookCreatedAtACertainTime_matcherRanWithADelayAfterOrderBookCreation_matcherRanWithNoMissMatch(self):
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                    ALTER SEQUENCE market_order_id_seq RESTART WITH 9090
                ''',
            )
        market = Market.by_symbol('BTCIRT')
        _create_orders_before_first_order_book_run(self.create_order, market)
        with patch(
            'django.utils.timezone.now', lambda: datetime.datetime.fromisoformat('2024-12-21 13:16:49.723775+00:00')
        ):
            OrderBookGenerator.run()
        _create_orders_after_first_order_book_run(self.create_order, market)
        with patch(
            'django.utils.timezone.now',
            lambda: datetime.datetime.fromisoformat('2024-12-21 13:16:50.769989+00:00'),
        ):
            matcher = Matcher(market)
            Matcher.MARKET_LAST_PROCESSED_TIME[market.id] = datetime.datetime.fromisoformat(
                '2024-12-21 13:16:48.621941+00:00',
            )
            matcher.price_range_high = 2866980
            matcher.price_range_low = 2851100
            matcher.do_matching_round()
            if market.symbol in Matcher.get_symbols_that_use_async_stop_process():
                post_processing_matcher_round(market, matcher.MARKET_PRICE_RANGE.get(market.id))

        OrderBookGenerator.run()

        with patch(
            'django.utils.timezone.now',
            lambda: datetime.datetime.fromisoformat('2024-12-21 13:16:51.792401+00:00'),
        ):
            matcher = Matcher(market)
            matcher.do_matching_round()
            if market.symbol in Matcher.get_symbols_that_use_async_stop_process():
                post_processing_matcher_round(market, matcher.MARKET_PRICE_RANGE.get(market.id))

        expected_order_matchings = [
            {'sale_id': 9090, 'buy_id': 9091},
            {'sale_id': 9103, 'buy_id': 9104},
            {'sale_id': 9103, 'buy_id': 9105},
            {'sale_id': 9093, 'buy_id': 9105},
            {'sale_id': 9093, 'buy_id': 9106},
            {'sale_id': 9093, 'buy_id': 9107},
            {'sale_id': 9093, 'buy_id': 9108},
            {'sale_id': 9093, 'buy_id': 9109},
            {'sale_id': 9094, 'buy_id': 9109},
            {'sale_id': 9095, 'buy_id': 9109},
            {'sale_id': 9095, 'buy_id': 9116},
            {'sale_id': 9096, 'buy_id': 9116},
            {'sale_id': 9096, 'buy_id': 9117},
            {'sale_id': 9096, 'buy_id': 9118},
            {'sale_id': 9096, 'buy_id': 9119},
            {'sale_id': 9096, 'buy_id': 9120},
            {'sale_id': 9096, 'buy_id': 9121},
            {'sale_id': 9096, 'buy_id': 9122},
            {'sale_id': 9096, 'buy_id': 9123},
            {'sale_id': 9096, 'buy_id': 9124},
            {'sale_id': 9096, 'buy_id': 9110},
            {'sale_id': 9096, 'buy_id': 9111},
            {'sale_id': 9096, 'buy_id': 9112},
            {'sale_id': 9096, 'buy_id': 9113},
            {'sale_id': 9096, 'buy_id': 9114},
            {'sale_id': 9096, 'buy_id': 9115},
            {'sale_id': 9097, 'buy_id': 9115},
            {'sale_id': 9098, 'buy_id': 9115},
            {'sale_id': 9099, 'buy_id': 9115},
            {'sale_id': 9100, 'buy_id': 9115},
            {'sale_id': 9101, 'buy_id': 9115},
            {'sale_id': 9102, 'buy_id': 9115},
            {'sale_id': 9092, 'buy_id': 9115},
        ]
        for item in expected_order_matchings:
            assert OrderMatching.objects.filter(sell_order=item['sale_id'], buy_order=item['buy_id']).exists()
        assert OrderMatching.objects.count() == len(expected_order_matchings)

    def test_orderBookCreatedAtCertainDatetime_marketOrderCreatedAfterOrderBook_marketOrderMatched(self):
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                    ALTER SEQUENCE market_order_id_seq RESTART WITH 9090
                ''',
            )
        market = Market.by_symbol('BTCIRT')
        sale_order = {
            'created_at': '2024-12-21 13:16:48.721756+00:00',
            'order_type': '1',
            'trade_type': '1',
            'price': '2866980',
            'amount': '352.413',
            'param1': '',
            'status': '3',
            'pair_id': '',
        }
        market_order = {
            'created_at': '2024-12-21 13:17:49.723775+00:00',
            'order_type': '2',
            'trade_type': '1',
            'price': '2866980',
            'amount': '4.001',
            'param1': '',
            'status': '2',
            'pair_id': '',
        }
        self.create_order(
            201,
            market,
            sale_order['amount'],
            sale_order['price'],
            'sell',
            sale_order['created_at'],
            is_market=False,
        )
        self.create_order(
            202,
            market,
            market_order['amount'],
            market_order['price'],
            'buy',
            market_order['created_at'],
            is_market=True,
        )
        OrderBookGenerator.run()

        with patch(
            'django.utils.timezone.now',
            lambda: datetime.datetime.fromisoformat('2024-12-21 13:18:50.769989+00:00'),
        ):
            matcher = Matcher(market)
            Matcher.MARKET_LAST_PROCESSED_TIME[market.id] = datetime.datetime.fromisoformat(sale_order['created_at'])
            matcher.price_range_high = 2866980
            matcher.price_range_low = 2851100
            matcher.do_matching_round()
            if market.symbol in Matcher.get_symbols_that_use_async_stop_process():
                post_processing_matcher_round(market, matcher.MARKET_PRICE_RANGE.get(market.id))

        assert OrderMatching.objects.count() == 1

    @patch.object(Matcher, 'ORDERBOOK_CRITERIA_AGE_VALIDITY_IN_SECONDS', 3600)
    def test_orderBookCreatedAtCertainTime_marketAndLimitOrderCreatedAfterOrderBook_ordersMatchedCorrectly(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                    ALTER SEQUENCE market_order_id_seq RESTART WITH 9090
                """
            )
        market = Market.by_symbol('BTCIRT')
        order_book_run_time = '2024-12-21 13:16:48.721756+00:00'
        sale_order = {
            'created_at': order_book_run_time,
            'order_type': '1',
            'trade_type': '1',
            'price': '2866980',
            'amount': '352.413',
            'param1': '',
            'status': '3',
            'pair_id': '',
        }
        buy_limit_order = {
            'created_at': '2024-12-21 13:17:48.721756+00:00',
            'order_type': '2',
            'trade_type': '1',
            'price': '2866990',
            'amount': '400',
            'param1': '',
            'status': '3',
            'pair_id': '',
        }
        buy_market_order = {
            'created_at': '2024-12-21 13:19:49.723775+00:00',
            'order_type': '2',
            'trade_type': '1',
            'price': '2866980',
            'amount': '4000.001',
            'param1': '',
            'status': '2',
            'pair_id': '',
        }
        sell_order_object = self.create_order(
            201,
            market,
            sale_order['amount'],
            sale_order['price'],
            'sell',
            sale_order['created_at'],
            is_market=False,
        )
        with patch('django.utils.timezone.now', lambda: datetime.datetime.fromisoformat(order_book_run_time)):
            OrderBookGenerator.run()
        limit_buy_order_object = self.create_order(
            202,
            market,
            buy_limit_order['amount'],
            buy_limit_order['price'],
            'buy',
            buy_limit_order['created_at'],
            is_market=False,
        )
        market_buy_order_object = self.create_order(
            202,
            market,
            buy_market_order['amount'],
            buy_market_order['price'],
            'buy',
            buy_market_order['created_at'],
            is_market=True,
        )

        with patch(
            'django.utils.timezone.now', lambda: datetime.datetime.fromisoformat('2024-12-21 13:20:50.769989+00:00')
        ):
            matcher = Matcher(market)
            matcher.price_range_high = 2866980
            matcher.price_range_low = 2851100
            matcher.do_matching_round()
            if market.symbol in Matcher.get_symbols_that_use_async_stop_process():
                post_processing_matcher_round(market, matcher.MARKET_PRICE_RANGE.get(market.id))
            assert not OrderMatching.objects.filter().exists()
        with patch(
            'django.utils.timezone.now', lambda: datetime.datetime.fromisoformat('2024-12-21 13:21:50.769989+00:00')
        ):
            OrderBookGenerator.run()
            matcher = Matcher(market)
            matcher.price_range_high = 2866980
            matcher.price_range_low = 2851100
            matcher.do_matching_round()
            if market.symbol in Matcher.get_symbols_that_use_async_stop_process():
                post_processing_matcher_round(market, matcher.MARKET_PRICE_RANGE.get(market.id))
            assert OrderMatching.objects.filter(sell_order=sell_order_object, buy_order=limit_buy_order_object).exists()
            assert OrderMatching.objects.count() == 1
