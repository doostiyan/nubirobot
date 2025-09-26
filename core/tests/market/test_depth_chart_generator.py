import json

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from exchange.base.models import Currencies
from exchange.market.depth_chart import MarketDepthChartGenerator
from exchange.market.models import Order, Market
from exchange.market.views import DepthChartAPI


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', }, })
class DepthChartTest(TestCase):

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

    def tearDown(self):
        Order.objects.all().delete()
        cache.clear()

    def test_create_depth_chart_generator(self):
        self.create_orders_list(Currencies.btc, Currencies.rls, Order.ORDER_TYPES.sell,
                                [817000000, 818750000, 819000000, 819005900],
                                [0.09022, 0.03, 0.17, 0.14281])
        self.create_orders_list(Currencies.btc, Currencies.rls, Order.ORDER_TYPES.buy,
                                [816450400, 816000000, 815990000, 815500000, 815281900, 815100000],
                                [0.54131, 1.03151, 0.57131, 0.16239, 0.24409, 0.27861])
        market = Market.by_symbol("BTCIRT")
        cache.set(f'market_{market.id}_last_price', 815100001)
        MarketDepthChartGenerator.generate_chart_for_symbol(market_symbol='BTCIRT')

        cached_depth = cache.get('depth_chart_BTCIRT')
        self.assertJSONEqual(
            cached_depth,
            '''{"ask": [["817000000", "0.09022"], ["818750000", "0.12022"], ["819000000", "0.29022"],
                       ["819006000", "0.43303"]],
                "bid": [["815100000", "2.82922"], ["815282000", "2.55061"], ["815500000", "2.30652"],
                       ["815990000", "2.14413"], ["816000000", "1.57282"], ["816450000", "0.54131"]],
                "last_trade_price": "815100001"
                }'''
        )

    def test_depth_chart_api(self):
        self.create_orders_list(Currencies.btc, Currencies.rls, Order.ORDER_TYPES.sell,
                                [817000000, 818750000, 819000000, 819005900],
                                [0.09022, 0.03, 0.17, 0.14281])
        self.create_orders_list(Currencies.btc, Currencies.rls, Order.ORDER_TYPES.buy,
                                [816450400, 816000000, 815990000, 815500000, 815281900, 815100000],
                                [0.54131, 1.03151, 0.57131, 0.16239, 0.24409, 0.27861])
        market = Market.by_symbol("BTCIRT")
        cache.set(f'market_{market.id}_last_price', 815100001)
        MarketDepthChartGenerator.generate_chart_for_symbol(market_symbol='BTCIRT')

        factory = APIRequestFactory()
        request = factory.get('v2/depth/BTCIRT')
        json_response = json.loads(DepthChartAPI.as_view()(request, 'BTCIRT').content)
        json_response.pop("lastUpdate")
        json_response.pop("status")

        self.assertDictEqual(json_response,
                             {"asks": [["817000000", "0.09022"], ["818750000", "0.12022"], ["819000000", "0.29022"],
                                       ["819006000", "0.43303"]],
                              "bids": [["815100000", "2.82922"], ["815282000", "2.55061"], ["815500000", "2.30652"],
                                       ["815990000", "2.14413"], ["816000000", "1.57282"], ["816450000", "0.54131"]],
                              "lastTradePrice": "815100001",

                              })

    def test_depth_chart_api_chart_not_cached(self):
        cache.delete(MarketDepthChartGenerator._get_cache_key("BTCUSDT"))
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
        market = Market.by_symbol("BTCUSDT")
        cache.set(f'market_{market.id}_last_price', 831)
        factory = APIRequestFactory()
        request = factory.get('v2/depth/BTCUSDT')
        json_response = json.loads(DepthChartAPI.as_view()(request, 'BTCUSDT').content)
        json_response.pop("lastUpdate")
        self.assertEqual(json_response.pop("status"), "ok")
        self.assertDictEqual(json_response,
                             {"asks": [["818", "10"], ["820", "110"], ["821", "1120"], ["830", "4120"]],
                              "bids": [["810", "5682"], ["815", "682"], ["816", "673"], ["817", "50"]],
                              "lastTradePrice": "831"})
