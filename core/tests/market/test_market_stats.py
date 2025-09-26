import json
from typing import Optional
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from exchange.base.models import AVAILABLE_CRYPTO_CURRENCIES, Currencies, get_currency_codename
from exchange.market.marketstats import MarketStats
from exchange.market.models import Market, MarketCandle


class MarketStatsAPITest(APITestCase):
    def tearDown(self):
        cache.clear()

    @staticmethod
    def create_market_candle(symbol, **kwargs):
        return MarketCandle.objects.create(
            market=Market.by_symbol(symbol),
            resolution=MarketCandle.RESOLUTIONS.hour,
            **kwargs
        )

    def get_market_stats(self, src_currencies: Optional[tuple] = None, dst_currencies: Optional[tuple] = None):
        data = {}
        if src_currencies:
            data['srcCurrency'] = ','.join(src_currencies)

        if dst_currencies:
            data['dstCurrency'] = ','.join(dst_currencies)
        response = self.client.get('/market/stats', data=data)
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        assert 'stats' in data
        return data['stats']

    @staticmethod
    def check_market_values(
        market_data,
        best_sell: str = '0',
        best_buy: str = '0',
        volume_src: str = '0',
        volume_dst: str = '0',
        day_low: str = '0',
        day_high: str = '0',
        day_open: str = '0',
        day_close: str = '0',
        day_change: str = '0',
    ):
        assert market_data['bestSell'] == best_sell
        assert market_data['bestBuy'] == best_buy
        assert market_data['volumeSrc'] == volume_src
        assert market_data['volumeDst'] == volume_dst
        assert market_data['dayLow'] == day_low
        assert market_data['dayHigh'] == day_high
        assert market_data['dayOpen'] == day_open
        assert market_data['dayClose'] == day_close
        assert market_data['dayChange'] == day_change
        assert market_data['latest'] == day_close


    def test_market_stats_no_candles(self):
        stats = self.get_market_stats(src_currencies=('btc', 'usdt', 'doge'), dst_currencies=('rls', 'usdt'))
        assert set(stats) == {'btc-rls', 'usdt-rls', 'doge-rls', 'btc-usdt', 'doge-usdt'}
        self.check_market_values(stats['btc-usdt'])


    def test_market_stats_one_candle(self):
        self.create_market_candle(
            'BTCUSDT', start_time=timezone.now(), trade_amount='3.76', trade_total='100020',
            open_price='26200', low_price='26105', high_price='26950', close_price='26700',
        )
        stats = self.get_market_stats(src_currencies=('btc', 'doge'), dst_currencies=('rls', 'usdt'))
        assert set(stats) == {'btc-rls', 'doge-rls', 'btc-usdt', 'doge-usdt'}
        self.check_market_values(
            stats['btc-usdt'], day_open='26200', day_close='26700', day_high='26950', day_low='26105',
            day_change='1.91', volume_src='3.76', volume_dst='100020',
        )
        self.check_market_values(stats['btc-rls'])


    def test_market_stats_multiple_candles(self):
        hour = timezone.timedelta(hours=1)
        self.create_market_candle(
            'DOGEIRT', start_time=timezone.now() - 23 * hour, trade_amount='1_600_000', trade_total='6_430_000_000_0',
            open_price='4_210_0', low_price='3_910_0', high_price='4_295_0', close_price='3_910_0',
        )
        self.create_market_candle(
            'DOGEIRT', start_time=timezone.now() - 5 * hour, trade_amount='1_000_000', trade_total='3_840_000_000_0',
            open_price='3_770_0', low_price='3_700_0', high_price='4_060_0', close_price='3_950_0',
        )
        self.create_market_candle(
            'DOGEIRT', start_time=timezone.now(), trade_amount='1_200_000', trade_total='4_560_000_000_0',
            open_price='3_815_0', low_price='3_790_0', high_price='3_985_0', close_price='3_810_0',
        )
        stats = self.get_market_stats(src_currencies=('doge',), dst_currencies=('rls', 'usdt'))
        assert set(stats) == {'doge-rls', 'doge-usdt'}
        self.check_market_values(
            stats['doge-rls'], day_open='42100', day_close='38100', day_high='42950', day_low='37000',
            day_change='-9.5', volume_src='3800000', volume_dst='148300000000',
        )
        self.check_market_values(stats['doge-usdt'])


    def test_market_stats_old_candles(self):
        hour = timezone.timedelta(hours=1)
        self.create_market_candle(
            'DOGEIRT', start_time=timezone.now() - 24 * hour, trade_amount='1_600_000', trade_total='6_430_000_000_0',
            open_price='4_210_0', low_price='3_910_0', high_price='4_295_0', close_price='3_910_0',
        )
        stats = self.get_market_stats(src_currencies=('usdt', 'doge'), dst_currencies=('rls',))
        assert set(stats) == {'usdt-rls', 'doge-rls'}
        self.check_market_values(stats['doge-rls'])

    def test_market_stats_best_active_prices(self):
        cache.set('orderbook_BTCUSDT_best_active_sell', '29700')
        cache.set('orderbook_BTCUSDT_best_active_buy', '26650')
        stats = self.get_market_stats(src_currencies=('btc', 'usdt'), dst_currencies=('rls', 'usdt'))
        assert set(stats) == {'btc-rls', 'usdt-rls', 'btc-usdt'}
        self.check_market_values(stats['btc-usdt'], best_sell='29700', best_buy='26650')

    def test_market_states_with_only_src_currencies_query_params(self):
        stats = self.get_market_stats(src_currencies=('btc', 'ltc'))

        assert len(stats) == 4
        assert all(currency_pairs.startswith('btc') or currency_pairs.startswith('ltc') for currency_pairs in stats)

    def test_market_states_with_only_dst_currencies_params(self):
        stats = self.get_market_stats(dst_currencies=('usdt',))

        # len(AVAILABLE_CRYPTO_CURRENCIES) - 1 -> usdt-usdt does not exists
        assert len(stats) == len(AVAILABLE_CRYPTO_CURRENCIES) - 1
        assert all(currency_pairs.endswith('usdt') for currency_pairs in stats)


class MarketStatsTest(TestCase):
    @patch('exchange.market.marketstats.MarketStats.calculate_market_stats_binance')
    @patch('exchange.market.marketstats.all_market_stats_publisher')
    @patch('exchange.market.marketstats.MarketStats.calculate_market_stats')
    def test_update_all_market_stats(
        self, mock_calculate_market_stats, mock_all_market_stats_publisher, mock_calculate_market_stats_binance
    ):
        market1, market2 = Market.objects.order_by('id')[:2]
        Market.objects.exclude(id__in=[market1.id, market2.id]).delete()

        mock_calculate_market_stats.side_effect = lambda market: '"21"' if market.symbol == market1.symbol else '"87"'

        MarketStats.update_all_market_stats()

        self.assertEqual(mock_calculate_market_stats.call_count, 2)
        mock_calculate_market_stats.assert_any_call(market1)
        mock_calculate_market_stats.assert_any_call(market2)

        mock_calculate_market_stats_binance.assert_called_once()

        mock_all_market_stats_publisher.assert_called_once()
        args, _ = mock_all_market_stats_publisher.call_args
        all_stats_data = json.loads(args[0])

        expected_all_stats_data = {
            f'{get_currency_codename(market1.src_currency)}-{get_currency_codename(market1.dst_currency)}': '21',
            f'{get_currency_codename(market2.src_currency)}-{get_currency_codename(market2.dst_currency)}': '87',
        }

        self.assertEqual(all_stats_data, expected_all_stats_data)
