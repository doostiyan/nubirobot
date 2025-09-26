import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.test import TestCase
from redis import RedisError

from exchange.base.models import Currencies
from exchange.wallet.estimator import PriceEstimator, XchangePriceEstimator
from exchange.xchange.models import MarketStatus


class MarketPriceEstimatorTest(TestCase):
    def setUp(self):
        PriceEstimator.get_price_range.clear()  # clean up

    def test_get_price_range(self):
        # Test special cases
        assert PriceEstimator.get_price_range(Currencies.rls) == (1, 1)
        # Test currencies without market
        assert PriceEstimator.get_price_range(Currencies.gala) == (0, 0)
        assert PriceEstimator.get_price_range(Currencies.pgala) == (0, 0)
        assert PriceEstimator.get_price_range(Currencies.flr) == (0, 0)
        # Test simple case of reading from cache
        cache.set('orderbook_XRPIRT_best_active_buy', Decimal('237010'))
        cache.set('orderbook_XRPIRT_best_active_sell', Decimal('237070'))
        assert PriceEstimator.get_price_range(Currencies.xrp) == (237010, 237070)
        # Price is cached in memory, so cache update should not affect it
        cache.set('orderbook_XRPIRT_best_active_buy', Decimal('237520'))
        cache.set('orderbook_XRPIRT_best_active_sell', Decimal('237800'))
        assert PriceEstimator.get_price_range(Currencies.xrp) == (237010, 237070)
        # Test another currency
        cache.set('orderbook_USDTIRT_best_active_buy', Decimal('243600'))
        cache.set('orderbook_USDTIRT_best_active_sell', Decimal('243650'))
        assert PriceEstimator.get_price_range(Currencies.usdt) == (243600, 243650)
        assert PriceEstimator.get_price_range(Currencies.xrp) == (237010, 237070)
        # Test lower digits
        cache.set('orderbook_DOGEIRT_best_active_buy', Decimal('95359'))
        cache.set('orderbook_DOGEIRT_best_active_sell', Decimal('95361'))
        assert PriceEstimator.get_price_range(Currencies.doge) == (95359, 95361)
        assert PriceEstimator.get_price_range(Currencies.usdt) == (243600, 243650)
        assert PriceEstimator.get_price_range(Currencies.xrp) == (237010, 237070)
        # Test zero price in cache
        cache.set('orderbook_DOGEIRT_best_active_buy', Decimal('0'))
        cache.set('orderbook_DOGEIRT_best_active_sell', Decimal('0'))
        cache.set('orderbook_USDTIRT_best_active_sell', Decimal('243800'))
        with patch('exchange.base.decorators.time', return_value=time.time() + 11):
            assert PriceEstimator.get_price_range(Currencies.doge) == (95359, 95361)
            assert PriceEstimator.get_price_range(Currencies.usdt) == (243600, 243800)
        # Test zero price with no cached value
        assert PriceEstimator.get_price_range(Currencies.ftm) == (0, 0)
        # Test tether values
        cache.set('orderbook_PMNUSDT_best_active_buy', Decimal('0.059'))
        cache.set('orderbook_PMNUSDT_best_active_sell', Decimal('0.062'))
        assert PriceEstimator.get_price_range(Currencies.pmn, Currencies.usdt) == (Decimal('0.059'), Decimal('0.062'))
        # Test rial values for currencies with no rial markets
        assert PriceEstimator.get_price_range(Currencies.pmn) == (14370, 15120)

    def test_get_rial_value_by_best_price(self):
        PriceEstimator.get_price_range.clear()  # prepare clean
        cache.set('orderbook_PMNUSDT_best_active_buy', Decimal('270_000'))
        cache.set('orderbook_PMNUSDT_best_active_sell', Decimal('271_000'))
        cache.set('orderbook_TRXIRT_best_active_buy', Decimal('30_000'))
        cache.set('orderbook_TRXIRT_best_active_sell', Decimal('31_000'))
        cache.set('orderbook_USDTIRT_best_active_buy', Decimal('17_710_0'))
        cache.set('orderbook_USDTIRT_best_active_sell', Decimal('17_730_0'))
        pmn_rial_value_buy = Decimal('270_000') * Decimal('17_710_0')
        pmn_rial_value_sell = Decimal('271_000') * Decimal('17_730_0')
        assert PriceEstimator.get_rial_value_by_best_price(1, Currencies.pmn, 'buy') == pmn_rial_value_buy
        assert PriceEstimator.get_rial_value_by_best_price(1, Currencies.pmn, 'sell') == pmn_rial_value_sell
        assert PriceEstimator.get_rial_value_by_best_price(3, Currencies.trx, 'buy') == Decimal('30_000') * 3
        assert PriceEstimator.get_rial_value_by_best_price(3, Currencies.trx, 'sell') == Decimal('31_000') * 3
        assert PriceEstimator.get_rial_value_by_best_price(10, Currencies.pmn, 'buy') == pmn_rial_value_buy * 10
        assert PriceEstimator.get_rial_value_by_best_price(15, Currencies.pmn, 'sell') == pmn_rial_value_sell * 15
        assert PriceEstimator.get_rial_value_by_best_price(10, Currencies.trx, 'buy') == Decimal('30_000') * 10
        assert PriceEstimator.get_rial_value_by_best_price(20, Currencies.trx, 'sell') == Decimal('31_000') * 20


class XchangePriceEstimatorTest(TestCase):
    def setUp(self):
        PriceEstimator.get_price_range.clear()  # clean up
        cache.clear()
        cache.set(
            'xchange_all_currency_pairs',
            [
                (Currencies.ren, Currencies.usdt),
                (Currencies.usdt, Currencies.ren),
                (Currencies.usdt, Currencies.bnt),
            ],
        )

    @patch('exchange.wallet.estimator.XCHANGE_CURRENCIES', [])
    def test_raise_error_for_non_xchange_coins(self):
        with pytest.raises(NotImplementedError):
            XchangePriceEstimator.get_price_range(Currencies.btc)

    @patch('exchange.wallet.estimator.XCHANGE_CURRENCIES', [Currencies.ren])
    def test_get_price_range_for_xchange_tradable_pair(self):
        self._create_or_update_market_status()
        assert XchangePriceEstimator.get_price_range(Currencies.ren, Currencies.usdt) == (
            Decimal('0.0604485'),
            Decimal('0.0592416'),
        )
        assert XchangePriceEstimator.get_price_range(Currencies.usdt, Currencies.ren) == (
            Decimal('16.5430076842'),
            Decimal('16.880030249'),
        )

    @patch('exchange.wallet.estimator.XCHANGE_CURRENCIES', [Currencies.ren])
    def test_get_price_range_for_the_same_pair(self):
        assert XchangePriceEstimator.get_price_range(Currencies.ren, Currencies.ren) == (Decimal(1), Decimal(1))

    @patch('exchange.wallet.estimator.XCHANGE_CURRENCIES', [Currencies.ren])
    def test_get_price_range_with_no_cached_price(self):
        self._create_or_update_market_status()
        cache.delete(f'xchange_pair_price_{Currencies.ren}_{Currencies.usdt}')
        assert XchangePriceEstimator.get_price_range(Currencies.ren, Currencies.usdt) == (Decimal('0'), Decimal('0'))
        assert XchangePriceEstimator.get_price_range(Currencies.usdt, Currencies.ren) == (
            Decimal('16.5430076842'),
            Decimal('16.880030249'),
        )

    @patch('exchange.wallet.estimator.cache.get', new_callable=MagicMock)
    @patch('exchange.wallet.estimator.XCHANGE_CURRENCIES', [Currencies.ren])
    def test_get_price_range_with_redis_error_using_db(self, mock_cache_get):
        def cache_get_with_error_raising(key, default=None, version=None):
            # to avoid infinite recursion, we don't use cache.get here and just define the behavior based on the keys
            if key == f'xchange_pair_price_{Currencies.ren}_{Currencies.usdt}':
                raise RedisError
            if key == 'xchange_all_currency_pairs':
                return [
                    (Currencies.ren, Currencies.usdt),
                    (Currencies.usdt, Currencies.ren),
                    (Currencies.usdt, Currencies.bnt),
                ]

        mock_cache_get.side_effect = cache_get_with_error_raising

        self._create_or_update_market_status()
        with pytest.raises(RedisError):
            XchangePriceEstimator.get_price_range(Currencies.ren, Currencies.usdt)
        assert XchangePriceEstimator.get_price_range(Currencies.ren, Currencies.usdt, db_fallback=True) == (
            Decimal('0.0604485'),
            Decimal('0.0592416'),
        )

    @patch('exchange.wallet.estimator.MarketPriceEstimator.get_price_range', new_callable=MagicMock)
    @patch('exchange.wallet.estimator.XCHANGE_CURRENCIES', [Currencies.ren])
    def test_get_price_range_for_not_xchange_tradable_pair_with_one_side_in_market(self, market_get_price_range):
        # (ren, rls) is not tradable in xchange but (ren, usdt) is, and (usdt, rls) is traded in market
        # price(ren, rls) = price(ren, usdt) * price(usdt, rls)
        self._create_or_update_market_status()
        market_get_price_range.return_value = (0, 0)
        assert XchangePriceEstimator.get_price_range(Currencies.ren, Currencies.rls) == (Decimal('0'), Decimal('0'))

        market_get_price_range.return_value = (59_000_0, 58_900_0)
        assert XchangePriceEstimator.get_price_range(Currencies.ren, Currencies.rls) == (
            Decimal('35664.615'),
            Decimal('34893.3024'),
        )
        market_get_price_range.assert_called_with(
            currency=Currencies.usdt, to_currency=Currencies.rls, db_fallback=False
        )

        # now (usdt, ren) is not tradable in xchange but (rls, ren) is, and (usdt, rls) is traded in market
        # price(usdt, ren) = price(usdt, rls) * price(rls, ren)
        cache.set('xchange_all_currency_pairs', [(Currencies.rls, Currencies.ren)])
        self._create_or_update_market_status(
            base_currency=Currencies.ren,
            quote_currency=Currencies.rls,
            base_to_quote_price_buy=Decimal('34770.0984'),
            quote_to_base_price_buy=Decimal('0.0000287603'),
            base_to_quote_price_sell=Decimal('34064.29026'),
            quote_to_base_price_sell=Decimal('0.0000293563'),
        )
        market_get_price_range.return_value = (0, 0)
        assert XchangePriceEstimator.get_price_range(Currencies.usdt, Currencies.ren) == (Decimal('0'), Decimal('0'))

        market_get_price_range.return_value = (59_000_0, 58_900_0)
        assert XchangePriceEstimator.get_price_range(Currencies.usdt, Currencies.ren, db_fallback=True) == (
            Decimal('16.968577'),
            Decimal('17.2908607'),
        )
        market_get_price_range.assert_called_with(
            currency=Currencies.usdt, to_currency=Currencies.rls, db_fallback=True
        )

    @patch('exchange.wallet.estimator.XCHANGE_CURRENCIES', [Currencies.ren, Currencies.bnt])
    def test_get_price_range_for_not_xchange_tradable_pair_with_both_sides_in_xchange(self):
        # (ren, bnt) is not directly tradable in xchange, but both (ren, usdt) and (usdt, bnt) are
        self._create_or_update_market_status()
        assert XchangePriceEstimator.get_price_range(Currencies.ren, Currencies.bnt) == (Decimal('0'), Decimal('0'))

        self._create_or_update_market_status(
            base_currency=Currencies.bnt,
            quote_currency=Currencies.usdt,
            base_to_quote_price_buy=Decimal('0.742047'),
            quote_to_base_price_buy=Decimal('1.3476235333'),
            base_to_quote_price_sell=Decimal('0.727254'),
            quote_to_base_price_sell=Decimal('1.3750354072'),
        )
        # price(ren, bnt) = price(ren, usdt) * price(usdt, bnt)
        assert XchangePriceEstimator.get_price_range(Currencies.ren, Currencies.bnt) == (
            Decimal('0.08146182115268505'),
            Decimal('0.08145929757917952'),
        )
        # (bnt, usdt) is not tradable in xchange, because it is not cached in 'xchange_all_currency_pairs' key
        assert XchangePriceEstimator.get_price_range(Currencies.bnt, Currencies.ren) == (Decimal(0), Decimal(0))

        cache.set(
            'xchange_all_currency_pairs',
            [
                (Currencies.ren, Currencies.usdt),
                (Currencies.usdt, Currencies.ren),
                (Currencies.usdt, Currencies.bnt),
                (Currencies.bnt, Currencies.usdt),
            ],
        )
        # price(bnt, ren) = price(bnt, usdt) * price(usdt, ren)
        assert XchangePriceEstimator.get_price_range(Currencies.bnt, Currencies.ren) == (
            Decimal('12.2756892230375574'),
            Decimal('12.276069518706246'),
        )

    def _create_or_update_market_status(
        self,
        base_currency: int = Currencies.ren,
        quote_currency: int = Currencies.usdt,
        base_to_quote_price_buy: Decimal = Decimal('0.0604485'),
        quote_to_base_price_buy: Decimal = Decimal('16.5430076842'),
        base_to_quote_price_sell: Decimal = Decimal('0.0592416'),
        quote_to_base_price_sell: Decimal = Decimal('16.880030249'),
    ):
        return MarketStatus.objects.update_or_create(
            base_currency=base_currency,
            quote_currency=quote_currency,
            defaults={
                'base_to_quote_price_buy': base_to_quote_price_buy,
                'quote_to_base_price_buy': quote_to_base_price_buy,
                'base_to_quote_price_sell': base_to_quote_price_sell,
                'quote_to_base_price_sell': quote_to_base_price_sell,
                'min_base_amount': Decimal(1),
                'max_base_amount': Decimal(100),
                'min_quote_amount': Decimal(1),
                'max_quote_amount': Decimal(100),
                'base_precision': Decimal('0.01'),
                'quote_precision': Decimal('0.01'),
                'status': MarketStatus.STATUS_CHOICES.available,
            },
        )
