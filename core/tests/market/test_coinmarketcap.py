from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import ONE_INCH, Currencies, AVAILABLE_MARKETS, ACTIVE_CRYPTO_CURRENCIES
from exchange.market import coinmarketcap
from exchange.market.models import MarketCandle, Market, Order
from tests.base.utils import CachedViewTestMixin, create_order, create_trade, do_matching_round


class CoinMarketCapMixin(CachedViewTestMixin):
    fixtures = ('system', 'test_data')

    BASE_URL = '/coinmarketcap/v1'
    CACHE_PREFIX = 'coinmarketcap'

    @staticmethod
    def create_market_candle(**kwargs):
        return MarketCandle.objects.create(
            market=Market.get_for(Currencies.btc, Currencies.rls),
            resolution=MarketCandle.RESOLUTIONS.minute,
            **kwargs
        )

    def setUp(self):
        self.patcher = patch(
            'exchange.market.coinmarketcap.CoinMarketCap.update_unified_cryptoasset_ids', self.mocked_coinmarketcap_api
        )
        self.mock_coinmarketcap_ids_update = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    @staticmethod
    def mocked_coinmarketcap_api():
        # if more complex tests are needed, the mocked function can be implemented here
        return


class TestMarketSummary(CoinMarketCapMixin, APITestCase):
    def test_basic_response_format(self):
        data = self.get_response('summary')
        assert isinstance(data, list)
        assert len(data) == len(AVAILABLE_MARKETS)
        assert AVAILABLE_MARKETS[0] == [Currencies.btc, Currencies.rls]
        assert data[0]['trading_pairs'] == 'BTC-IRR'
        assert data[0]['base_currency'] == 'BTC'
        assert data[0]['quote_currency'] == 'IRR'
        assert 'last_price' in data[0]
        assert 'lowest_ask' in data[0]
        assert 'highest_bid' in data[0]
        assert 'base_volume' in data[0]
        assert 'quote_volume' in data[0]
        assert 'price_change_percent_24h' in data[0]
        assert 'highest_price_24h' in data[0]
        assert 'lowest_price_24h' in data[0]

    def test_empty_market_data(self):
        data = self.get_response('summary')
        assert data
        assert data[0]['trading_pairs'] == 'BTC-IRR'
        assert data[0]['base_volume'] == '0'
        assert data[0]['quote_volume'] == '0'
        assert data[0]['price_change_percent_24h'] == '0'
        assert data[0]['highest_price_24h'] == '0'
        assert data[0]['lowest_price_24h'] == '0'

    def test_single_market_data(self):
        now = timezone.now()
        self.create_market_candle(
            start_time=now,
            open_price=1_150_000_000_0,
            close_price=1_155_000_000_0,
            low_price=1_148_000_000_0,
            high_price=1_157_000_000_0,
            trade_amount='0.36',
            trade_total=415_080_000_0,
        )
        data = self.get_response('summary')
        assert data
        assert data[0]['trading_pairs'] == 'BTC-IRR'
        assert Decimal(data[0]['base_volume']) == Decimal('0.36')
        assert Decimal(data[0]['quote_volume']) == 415_080_000_0
        assert Decimal(data[0]['price_change_percent_24h']) == Decimal('0.43')
        assert Decimal(data[0]['highest_price_24h']) == 1_157_000_000_0
        assert Decimal(data[0]['lowest_price_24h']) == 1_148_000_000_0

    def test_multiple_market_data(self):
        now = ir_now()
        self.create_market_candle(
            start_time=now,
            open_price=1_156_000_000_0,
            close_price=1_155_000_000_0,  # 24h close price
            low_price=1_154_000_000_0,
            high_price=1_156_000_000_0,
            trade_amount='0.12',
            trade_total=138_600_000_0,
        )
        self.create_market_candle(
            start_time=now - timezone.timedelta(hours=6),
            open_price=1_149_000_000_0,
            close_price=1_156_000_000_0,
            low_price=1_149_000_000_0,
            high_price=1_157_000_000_0,  # highest price
            trade_amount='0.15',
            trade_total=172_980_000_0,
        )
        self.create_market_candle(
            start_time=now - timezone.timedelta(hours=20),
            open_price=1_150_000_000_0,  # 24h open price
            close_price=1_149_000_000_0,
            low_price=1_148_000_000_0,  # lowest price
            high_price=1_151_000_000_0,
            trade_amount='0.09',
            trade_total=103_500_000_0,
        )
        data = self.get_response('summary')
        assert data
        assert data[0]['trading_pairs'] == 'BTC-IRR'
        assert Decimal(data[0]['base_volume']) == Decimal('0.36')
        assert Decimal(data[0]['quote_volume']) == 415_080_000_0
        assert Decimal(data[0]['price_change_percent_24h']) == Decimal('0.43')
        assert Decimal(data[0]['highest_price_24h']) == 1_157_000_000_0
        assert Decimal(data[0]['lowest_price_24h']) == 1_148_000_000_0

    def test_empty_orderbook_cache(self):
        cache.delete('orderbook_BTCIRT_last_trade_price', '')
        cache.delete('orderbook_BTCIRT_bids', '[]')
        cache.delete('orderbook_BTCIRT_asks', '[]')
        data = self.get_response('summary')
        assert data
        assert data[0]['trading_pairs'] == 'BTC-IRR'
        assert data[0]['last_price'] == '0'
        assert data[0]['lowest_ask'] == '0'
        assert data[0]['highest_bid'] == '0'

    def test_empty_orderbook_data(self):
        cache.set('orderbook_BTCIRT_last_trade_price', '')
        cache.set('orderbook_BTCIRT_bids', '[]')
        cache.set('orderbook_BTCIRT_asks', '[]')
        data = self.get_response('summary')
        assert data
        assert data[0]['trading_pairs'] == 'BTC-IRR'
        assert data[0]['last_price'] == '0'
        assert data[0]['lowest_ask'] == '0'
        assert data[0]['highest_bid'] == '0'

    def test_full_orderbook_data(self):
        cache.set('orderbook_BTCIRT_last_trade_price', '11548000000')
        cache.set('orderbook_BTCIRT_bids', '[["11560000000","0.01"],["11570000000","0.007"]]')
        cache.set('orderbook_BTCIRT_asks', '[["11530000000","0.006"],["11520000000","0.013"]]')

        data = self.get_response('summary')
        assert data
        assert data[0]['trading_pairs'] == 'BTC-IRR'
        assert data[0]['last_price'] == '11548000000'
        assert data[0]['lowest_ask'] == '11560000000'
        assert data[0]['highest_bid'] == '11530000000'


class TestMarketAssets(CoinMarketCapMixin, APITestCase):
    def test_basic_response_format(self):
        data = self.get_response('assets')
        assert isinstance(data, dict)
        assert len(data) == len(ACTIVE_CRYPTO_CURRENCIES)
        assert 'BTC' in data
        assert data['BTC']['name'] == 'Bitcoin'
        assert data['BTC']['unified_cryptoasset_id'] == 1
        assert 'can_withdraw' in data['BTC']
        assert 'can_deposit' in data['BTC']
        assert 'min_withdraw' in data['BTC']
        assert 'max_withdraw' in data['BTC']
        assert data['BTC']['maker_fee'] == '0.25'
        assert data['BTC']['taker_fee'] == '0.25'

    @patch.dict(coinmarketcap.NOBITEX_OPTIONS['minWithdraws'], {Currencies.btc: Decimal('0.1')})
    @patch.dict(coinmarketcap.NOBITEX_OPTIONS['maxWithdraws'], {Currencies.btc: Decimal('1')})
    @patch.dict(coinmarketcap.CURRENCY_INFO, {Currencies.btc: {'network_list': {}}})
    def test_on_no_network(self, *mocks):
        data = self.get_response('assets')
        assert data
        assert not data['BTC']['can_withdraw']
        assert not data['BTC']['can_deposit']
        assert data['BTC']['min_withdraw'] == '0.1'
        assert data['BTC']['max_withdraw'] == '0'

    @patch.dict(coinmarketcap.CURRENCY_INFO, {Currencies.btc: {'network_list': {
        'BTC': {'withdraw_max': '1', 'withdraw_min': '0.000001'},
    }}})
    def test_can_deposit_or_withdraw_on_enabled_by_default_network(self, *mocks):
        data = self.get_response('assets')
        assert data
        assert data['BTC']['can_withdraw']
        assert data['BTC']['can_deposit']

    @patch.dict(coinmarketcap.CURRENCY_INFO, {Currencies.btc: {'network_list': {
        'BTC': {'deposit_enable': False, 'withdraw_enable': False, 'withdraw_max': '1', 'withdraw_min': '0.000001'},
        'BSC': {'deposit_enable': False, 'withdraw_enable': True, 'withdraw_max': '0.5', 'withdraw_min': '0.00001'},
    }}})
    def test_can_deposit_or_withdraw_on_no_deposit_enabled_network(self, *mocks):
        data = self.get_response('assets')
        assert data
        assert data['BTC']['can_withdraw']
        assert not data['BTC']['can_deposit']

    @patch.dict(coinmarketcap.CURRENCY_INFO, {Currencies.btc: {'network_list': {
        'BTC': {'deposit_enable': True, 'withdraw_enable': False, 'withdraw_max': '1', 'withdraw_min': '0.000001'},
        'BSC': {'deposit_enable': False, 'withdraw_enable': False, 'withdraw_max': '0.5', 'withdraw_min': '0.00001'},
    }}})
    def test_can_deposit_or_withdraw_on_no_withdraw_enabled_network(self, *mocks):
        data = self.get_response('assets')
        assert data
        assert not data['BTC']['can_withdraw']
        assert data['BTC']['can_deposit']

    @patch.dict(coinmarketcap.NOBITEX_OPTIONS['minWithdraws'], {Currencies.btc: Decimal('0.0000005')})
    @patch.dict(coinmarketcap.CURRENCY_INFO, {Currencies.btc: {'network_list': {
        'BTC': {'withdraw_max': '1', 'withdraw_min': '0.000001'},
        'BSC': {'withdraw_max': '1', 'withdraw_min': '0.00001'},
    }}})
    def test_min_withdraw_on_nobitex_min_below_networks_min(self, *mocks):
        data = self.get_response('assets')
        assert data
        assert data['BTC']['min_withdraw'] == '0.000001'

    @patch.dict(coinmarketcap.NOBITEX_OPTIONS['minWithdraws'], {Currencies.btc: Decimal('0.000005')})
    @patch.dict(coinmarketcap.CURRENCY_INFO, {Currencies.btc: {'network_list': {
        'BTC': {'withdraw_max': '1', 'withdraw_min': '0.000001'},
        'BSC': {'withdraw_max': '1', 'withdraw_min': '0.00001'},
    }}})
    def test_min_withdraw_on_nobitex_min_above_networks_min(self, *mocks):
        data = self.get_response('assets')
        assert data
        assert data['BTC']['min_withdraw'] == '0.000005'

    @patch.dict(coinmarketcap.NOBITEX_OPTIONS['maxWithdraws'], {Currencies.btc: Decimal('0.5')})
    @patch.dict(coinmarketcap.CURRENCY_INFO, {Currencies.btc: {'network_list': {
        'BTC': {'withdraw_max': '0.1', 'withdraw_min': '0.00001'},
        'BSC': {'withdraw_max': '1.0', 'withdraw_min': '0.00001'},
    }}})
    def test_max_withdraw_on_nobitex_max_below_networks_max(self, *mocks):
        data = self.get_response('assets')
        assert data
        assert data['BTC']['max_withdraw'] == '0.5'

    @patch.dict(coinmarketcap.NOBITEX_OPTIONS['maxWithdraws'], {Currencies.btc: Decimal('1.5')})
    @patch.dict(coinmarketcap.CURRENCY_INFO, {Currencies.btc: {'network_list': {
        'BTC': {'withdraw_max': '0.1', 'withdraw_min': '0.00001'},
        'BSC': {'withdraw_max': '1.0', 'withdraw_min': '0.00001'},
    }}})
    def test_max_withdraw_on_nobitex_max_above_networks_max(self, *mocks):
        data = self.get_response('assets')
        assert data
        assert data['BTC']['max_withdraw'] == '1.1'

    @patch.dict(coinmarketcap.NOBITEX_OPTIONS['minWithdraws'], {Currencies.btc: Decimal('0.000001')})
    @patch.dict(coinmarketcap.NOBITEX_OPTIONS['maxWithdraws'], {Currencies.btc: Decimal('1.5')})
    @patch.dict(coinmarketcap.CURRENCY_INFO, {Currencies.btc: {'network_list': {
        'BTC': {'withdraw_max': '0.1', 'withdraw_min': '0.000001', 'withdraw_enable': False},
        'BSC': {'withdraw_max': '1.0', 'withdraw_min': '0.00001'},
    }}})
    def test_min_max_withdraw_on_withdraw_disabled_network(self, *mocks):
        data = self.get_response('assets')
        assert data
        assert data['BTC']['min_withdraw'] == '0.00001'
        assert data['BTC']['max_withdraw'] == '1'

    @pytest.mark.slow
    @patch.object(coinmarketcap, 'ACTIVE_CRYPTO_CURRENCIES', [Currencies.dodo, ONE_INCH])
    @patch.dict(coinmarketcap.NOBITEX_OPTIONS['maxWithdraws'], {Currencies.dodo: 100, ONE_INCH: 100})
    @patch.dict(coinmarketcap.NOBITEX_OPTIONS['minWithdraws'], {Currencies.dodo: 1, ONE_INCH: 1})
    def test_new_crypto_currency_launch(self, *mocks):
        with pytest.warns(UserWarning):
            data = self.get_response('assets')
        assert len(data) == 2
        assert 'DODO' in data
        assert data['DODO']['unified_cryptoasset_id'] == 7224
        assert '1INCH' in data
        assert data['1INCH']['unified_cryptoasset_id'] == 8104


class TestMarketTicker(CoinMarketCapMixin, APITestCase):
    def test_basic_response_format(self):
        data = self.get_response('ticker')
        assert isinstance(data, dict)
        assert len(data) == len(AVAILABLE_MARKETS)
        assert 'BTC-IRR' in data
        assert data['BTC-IRR']['base_id'] == 1
        assert data['BTC-IRR']['quote_id'] == 3544
        assert 'last_price' in data['BTC-IRR']
        assert 'base_volume' in data['BTC-IRR']
        assert 'quote_volume' in data['BTC-IRR']
        assert data['BTC-IRR']['isFrozen'] == 0

    def test_empty_market_data(self):
        data = self.get_response('ticker')
        assert data
        assert data['BTC-IRR']['base_volume'] == '0'
        assert data['BTC-IRR']['quote_volume'] == '0'

    def test_single_market_data(self):
        now = timezone.now()
        self.create_market_candle(start_time=now, trade_amount='0.36', trade_total=415_080_000_0)
        data = self.get_response('ticker')
        assert data
        assert Decimal(data['BTC-IRR']['base_volume']) == Decimal('0.36')
        assert Decimal(data['BTC-IRR']['quote_volume']) == 415_080_000_0

    def test_multiple_market_data(self):
        now = ir_now()
        hour = timezone.timedelta(hours=1)
        self.create_market_candle(start_time=now, trade_amount='0.12', trade_total=138_600_000_0)
        self.create_market_candle(start_time=now - 6 * hour, trade_amount='0.15', trade_total=172_980_000_0)
        self.create_market_candle(start_time=now - 20 * hour, trade_amount='0.09', trade_total=103_500_000_0)
        data = self.get_response('ticker')
        assert data
        assert Decimal(data['BTC-IRR']['base_volume']) == Decimal('0.36')
        assert Decimal(data['BTC-IRR']['quote_volume']) == 415_080_000_0

    def test_empty_orderbook_cache(self):
        cache.delete('orderbook_BTCIRT_last_trade_price')
        data = self.get_response('ticker')
        assert data
        assert data['BTC-IRR']['last_price'] == '0'

    def test_empty_orderbook_data(self):
        cache.set('orderbook_BTCIRT_last_trade_price', '')
        data = self.get_response('ticker')
        assert data
        assert data['BTC-IRR']['last_price'] == '0'

    def test_full_orderbook_data(self):
        cache.set('orderbook_BTCIRT_last_trade_price', '11548000000')
        data = self.get_response('ticker')
        assert data
        assert data['BTC-IRR']['last_price'] == '11548000000'

    def test_is_frozen_for_inactive_market(self):
        Market.objects.update_or_create(
            src_currency=Currencies.btc, dst_currency=Currencies.rls, defaults={'is_active': False, 'pk': 1}
        )
        data = self.get_response('ticker')
        assert data
        assert data['BTC-IRR']['isFrozen'] == 1


class TestOrderBook(CoinMarketCapMixin, APITestCase):

    @staticmethod
    def create_orders_list(tp, pairs):
        orders = [
            Order(
                user_id=201 + i % 4,
                src_currency=Currencies.btc,
                dst_currency=Currencies.rls,
                order_type=tp,
                price=price,
                amount=amount,
                status=Order.STATUS.active,
            )
            for i, (price, amount) in enumerate(pairs)
        ]
        Order.objects.bulk_create(orders)

    def test_basic_response_format(self):
        data = self.get_response('orderbook/BTC-IRR')
        assert isinstance(data, dict)
        assert 'timestamp' in data
        assert 'bids' in data and isinstance(data['bids'], list)
        assert 'asks' in data and isinstance(data['asks'], list)

    def test_orderbook_with_unlimited_depth(self):
        bids = [
            ["11530000000", "0.06"],
            ["11520000000", "0.04"],
            ["11510000000", "0.01"],
        ]
        asks = [
            ["11560000000", "0.01"],
            ["11570000000", "0.02"],
            ["11580000000", "0.01"],
            ["11590000000", "0.03"],
        ]
        self.create_orders_list(Order.ORDER_TYPES.sell, asks)
        self.create_orders_list(Order.ORDER_TYPES.buy, bids)
        start = timezone.now().timestamp() * 1000
        data = self.get_response('orderbook/BTC-IRR')
        end = timezone.now().timestamp() * 1000
        assert data
        assert start < data['timestamp'] < end
        assert data['bids'] == bids
        assert data['asks'] == asks

    def test_orderbook_with_unlimited_depth_and_unmatched_orders(self):
        bids = [
            ["11560000000", "0.01"],
            ["11530000000", "0.06"],
            ["11530000000", "0.01"],
            ["11520000000", "0.04"],
        ]
        asks = [
            ["11560000000", "0.02"],
            ["11570000000", "0.03"],
        ]
        self.create_orders_list(Order.ORDER_TYPES.sell, asks)
        self.create_orders_list(Order.ORDER_TYPES.buy, bids)
        data = self.get_response('orderbook/BTC-IRR')
        assert data
        assert data['bids'] == [["11530000000", "0.07"], ["11520000000", "0.04"]]
        assert data['asks'] == [["11560000000", "0.01"], ["11570000000", "0.03"]]

    def test_orderbook_with_limited_depth_below_max_size_and_no_cache(self):
        cache.delete_many(['orderbook_BTCIRT_bids', 'orderbook_BTCIRT_asks', 'orderbook_BTCIRT_update_time'])
        data = self.get_response('orderbook/BTC-IRR?depth=10')
        assert data
        assert data['timestamp'] == 0
        assert data['bids'] == []
        assert data['asks'] == []

    def test_orderbook_with_limited_depth_below_max_size_and_cached_data(self):
        cache.set('orderbook_BTCIRT_update_time', '1648299700000')
        cache.set(
            'orderbook_BTCIRT_bids',
            '[["11560000000","0.01"],["11570000000","0.02"],["11580000000","0.01"],["11590000000","0.03"]'
            ',["11600000000","0.02"],["11610000000","0.03"],["11620000000","0.07"],["11630000000","0.01"]]'
        )
        cache.set(
            'orderbook_BTCIRT_asks',
            '[["11530000000","0.06"],["11520000000","0.04"],["11510000000","0.01"],["11500000000","0.03"]'
            ',["11490000000","0.02"],["11480000000","0.01"],["11470000000","0.03"],["11460000000","0.04"]]'
        )
        data = self.get_response('orderbook/BTC-IRR?depth=10')
        assert data
        assert data['timestamp'] == 1648299700000
        print(data['asks'])
        assert data['asks'] == [
            ["11560000000", "0.01"],
            ["11570000000", "0.02"],
            ["11580000000", "0.01"],
            ["11590000000", "0.03"],
            ["11600000000", "0.02"],
        ]
        assert data['bids'] == [
            ["11530000000", "0.06"],
            ["11520000000", "0.04"],
            ["11510000000", "0.01"],
            ["11500000000", "0.03"],
            ["11490000000", "0.02"],
        ]

    def test_orderbook_with_limited_depth_above_max_size_and_cached_data(self):
        cache.set('orderbook_BTCIRT_update_time', '1648299700000')
        cache.set(
            'orderbook_BTCIRT_bids',
            '[["11560000000","0.01"],["11570000000","0.02"],["11580000000","0.01"],["11590000000","0.03"]]'
        )
        cache.set(
            'orderbook_BTCIRT_asks',
            '[["11530000000","0.06"],["11520000000","0.04"],["11510000000","0.01"],["11500000000","0.03"]]'
        )
        bids = [
            ["11530000000", "0.06"],
            ["11520000000", "0.04"],
            ["11510000000", "0.01"],
            ["11500000000", "0.03"],
            ["11490000000", "0.02"],
        ]
        asks = [
            ["11560000000", "0.01"],
            ["11570000000", "0.02"],
            ["11580000000", "0.01"],
            ["11590000000", "0.03"],
            ["11600000000", "0.02"],
            ["11610000000", "0.03"],
        ]
        self.create_orders_list(Order.ORDER_TYPES.sell, asks)
        self.create_orders_list(Order.ORDER_TYPES.buy, bids)
        start = timezone.now().timestamp() * 1000
        data = self.get_response('orderbook/BTC-IRR?depth=100')
        end = timezone.now().timestamp() * 1000
        assert data
        assert start < data['timestamp'] < end
        assert data['bids'] == bids
        assert data['asks'] == asks

    def test_orderbook_with_first_item_level_and_cached_data(self):
        cache.set('orderbook_BTCIRT_update_time', '1648299700000')
        cache.set('orderbook_BTCIRT_bids', '[["11560000000","0.01"],["11570000000","0.02"],["11580000000","0.01"]]')
        cache.set('orderbook_BTCIRT_asks', '[["11530000000","0.06"],["11520000000","0.04"],["11510000000","0.01"]]')
        data = self.get_response('orderbook/BTC-IRR?level=1')
        assert data
        assert data['timestamp'] == 1648299700000
        print(data['asks'])
        assert data['asks'] == [["11560000000", "0.01"]]
        assert data['bids'] == [["11530000000", "0.06"]]

    def test_orderbook_with_wrong_trading_pair(self):
        for symbol in ('BTCIRR', 'BTC_IRR', 'BTC-IRT'):
            data = self.get_response(f'orderbook/{symbol}')
            assert data['status'] == 'failed'
            assert data['code'] == 'ParseError'

    def test_orderbook_with_wrong_depth(self):
        for depth in ('ten', '10.5', '12', '1000000'):
            data = self.get_response(f'orderbook/BTC-IRR?depth={depth}')
            assert data['status'] == 'failed'
            assert data['code'] == 'ParseError'

    def test_orderbook_with_wrong_level(self):
        for level in ('pro', '5', ' ', '-2'):
            data = self.get_response(f'orderbook/BTC-IRR?level={level}')
            assert data['status'] == 'failed'
            assert data['code'] == 'ParseError'


class TestTrades(CoinMarketCapMixin, APITestCase):

    def setUp(self):
        self.user1 = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=201)

    def test_basic_response_format(self):
        trade = create_trade(self.user1, self.user2, Currencies.btc, Currencies.rls, amount='0.01', price='11540000000')
        data = self.get_response('trades/BTC-IRR')
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]['trade_id'] == trade.id
        assert data[0]['price'] == '11540000000'
        assert data[0]['base_volume'] == '0.01'
        assert data[0]['quote_volume'] == '115400000'
        assert data[0]['timestamp'] == int(trade.created_at.timestamp() * 1000)
        assert data[0]['type'] in ('Buy', 'Sell')

    def test_trades_with_older_time(self):
        trade = create_trade(self.user1, self.user2, Currencies.btc, Currencies.rls, amount='0.01', price='11540000000')
        trade.created_at -= timezone.timedelta(hours=10)
        trade.save(update_fields=['created_at'])
        data = self.get_response('trades/BTC-IRR')
        assert not data

    def test_trades_trade_type(self):
        market = Market.get_for(Currencies.btc, Currencies.rls)
        create_order(self.user1, Currencies.btc, Currencies.rls, amount='0.02', price='11545000000', sell=True)
        create_order(
            self.user2, Currencies.btc, Currencies.rls, amount='0.03', price='11550000000', sell=False, market=True,
        )
        do_matching_round(market)
        create_order(self.user1, Currencies.btc, Currencies.rls, amount='0.01', price='11535000000', sell=False)
        create_order(
            self.user2, Currencies.btc, Currencies.rls, amount='0.02', price='11530000000', sell=True, market=True,
        )
        do_matching_round(market)
        data = self.get_response('trades/BTC-IRR')
        assert len(data) == 2
        # Last match
        assert data[0]['base_volume'] == '0.01'
        assert data[0]['price'] == '11535000000'
        assert data[0]['type'] == 'Sell'
        # First match
        assert data[1]['base_volume'] == '0.02'
        assert data[1]['price'] == '11545000000'
        assert data[1]['type'] == 'Buy'

    def test_trades_with_wrong_trading_pair(self):
        for symbol in ('BTCIRR', 'BTC_IRR', 'BTC-IRT'):
            data = self.get_response(f'trades/{symbol}')
            assert data['status'] == 'failed'
            assert data['code'] == 'ParseError'
