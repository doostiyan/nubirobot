
from django.core.cache import cache
from django.test import TestCase

from exchange.base.models import VALID_MARKET_SYMBOLS, parse_market_symbol
from exchange.market.models import Market
from exchange.matcher.divider import custom_partition_markets


class TestMatcherSeparationMarkets(TestCase):
    def setUp(self):
        cache.set('settings_concurrent_matcher_status', 'enabled')
        return super().setUp()

    def tearDown(self):
        cache.clear()
        return super().tearDown()

    def _create_markets(self, symbols):
        markets = []
        for symbol in symbols:
            src, dst = parse_market_symbol(symbol)
            markets.append(Market(src_currency=src, dst_currency=dst, is_active=True))
        return {market.symbol: market for market in Market.objects.bulk_create(markets)}

    @staticmethod
    def check_lists(markets, expected_markets_symbols):
        assert len(markets) == len(expected_markets_symbols)
        assert all(s.symbol in expected_markets_symbols for s in markets)

    def test_separation_markets_with_empty_list(self):
        cache.set('settings_concurrent_matcher_status', 'disabled')
        markets = self._create_markets(('BTCIRT', 'BTCUSDT', 'TIRT', 'TUSDT'))
        assert len(markets) == 4
        separated_markets = custom_partition_markets(markets)
        assert len(separated_markets[0]) == 4
        assert len(separated_markets[1]) == 0
        assert len(separated_markets[2]) == 0
        assert len(separated_markets[3]) == 0
        assert len(separated_markets[4]) == 0

    def test_separation_markets_1(self):
        markets = self._create_markets(('TIRT', 'TUSDT', 'USDTIRT'))
        assert len(markets) == 3
        separated_markets = custom_partition_markets(markets)
        assert [s.symbol for s in separated_markets[0]] == ['USDTIRT']
        self.check_lists(separated_markets[1], {'TIRT'})
        assert len(separated_markets[2]) == 0
        assert len(separated_markets[3]) == 0
        self.check_lists(separated_markets[4], {'TUSDT'})


    def test_separation_markets_3(self):
        markets = self._create_markets(('BTCIRT', 'BTCUSDT', 'TIRT', 'TUSDT', 'USDTIRT', 'XMRUSDT', 'ETHUSDT'))
        assert len(markets) == 7
        separated_markets = custom_partition_markets(markets)
        assert [s.symbol for s in separated_markets[0]] == ['USDTIRT']
        assert len(separated_markets[1]) == 2
        self.check_lists(separated_markets[1], {'BTCUSDT', 'TUSDT'})
        assert len(separated_markets[2]) == 0
        self.check_lists(separated_markets[3], {'XMRUSDT', 'ETHUSDT'})
        self.check_lists(separated_markets[4], {'BTCIRT', 'TIRT'})

    def test_separation_markets_4(self):
        cache.set('settings_concurrent_matcher_status', 'enabled')
        markets = self._create_markets(
            ('BTCIRT', 'BTCUSDT', 'TIRT', 'TUSDT', 'USDTIRT', 'XMRUSDT', 'ETHUSDT', '1M_PEPEIRT', 'NOTIRT', 'WIRT'),
        )
        assert len(markets) == 10
        separated_markets = custom_partition_markets(markets)
        assert [s.symbol for s in separated_markets[0]] == ['USDTIRT']
        self.check_lists(separated_markets[1], {'BTCIRT', 'TIRT', '1M_PEPEIRT'})
        self.check_lists(separated_markets[2], {'XMRUSDT', 'ETHUSDT'})
        self.check_lists(separated_markets[3], {'NOTIRT', 'WIRT'})
        self.check_lists(separated_markets[4], {'BTCUSDT', 'TUSDT'})


    def test_separation_markets_5(self):
        markets = self._create_markets(
            (
                'USDTIRT',
                'XMRIRT',
                'ETHIRT',
                '1M_PEPEIRT',
                'BTCIRT',
                'SHIBIRT',
                'TIRT',
                'NOTUSDT',
                'WUSDT',
                'BTCUSDT',
                'DOGEUSDT',
                'TUSDT',
            ),
        )
        assert len(markets) == 12
        separated_markets = custom_partition_markets(markets)
        assert [s.symbol for s in separated_markets[0]] == ['USDTIRT']

        self.check_lists(separated_markets[1], {'XMRIRT', 'ETHIRT', '1M_PEPEIRT'})
        self.check_lists(separated_markets[2], {'NOTUSDT', 'WUSDT', 'BTCUSDT', 'DOGEUSDT', 'TUSDT'})
        self.check_lists(separated_markets[3], {'BTCIRT', 'SHIBIRT', 'TIRT'})
        self.check_lists(separated_markets[4], {})

    def test_full_markets(self):
        all_possible_markets = VALID_MARKET_SYMBOLS.copy()
        markets = self._create_markets(all_possible_markets)
        all_possible_markets.remove('USDTIRT')

        separated_markets = custom_partition_markets(markets)
        assert [s.symbol for s in separated_markets[0]] == ['USDTIRT']

        part_symbols = [[market.symbol for market in part] for part in separated_markets[1:]]

        for symbol in all_possible_markets:
            assert sum([symbol in part for part in part_symbols]) == 1
