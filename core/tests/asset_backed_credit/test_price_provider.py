from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

import pytest
import responses

from exchange.asset_backed_credit.exceptions import PriceNotAvailableError
from exchange.asset_backed_credit.externals.price import MarketStatAPI, PriceProvider, price_cache
from exchange.base.models import Currencies, Settings
from exchange.market.models import Market


class PriceProviderTests(TestCase):
    def setUp(self):
        self.market_stats_btc_rls_price = {
            "stats": {
                "btc-rls": {
                    "isClosed": False,
                    "bestSell": "61349.8",
                    "bestBuy": "61267",
                    "volumeSrc": "11.956031363825",
                    "volumeDst": "737569.147795258975",
                    "latest": "61267.03",
                    "mark": "61392.82",
                    "dayLow": "60170",
                    "dayHigh": "63999.1",
                    "dayOpen": "63997.99",
                    "dayClose": "61267.03",
                    "dayChange": "-4.27",
                },
            },
            "global": {
                "binance": {
                    "c98": '0.1355',
                }
            },
        }

        self.market_stats_btc_usdt_price = {
            "stats": {
                "btc-usdt": {
                    "isClosed": False,
                    "bestSell": "61349.8",
                    "bestBuy": "61267",
                    "volumeSrc": "11.956031363825",
                    "volumeDst": "737569.147795258975",
                    "latest": "61267.03",
                    "mark": "61392.82",
                    "dayLow": "60170",
                    "dayHigh": "63999.1",
                    "dayOpen": "63997.99",
                    "dayClose": "61267.03",
                    "dayChange": "-4.27",
                },
            },
            "global": {
                "binance": {
                    "c98": '0.1355',
                }
            },
        }

        self.src_currency = Currencies.btc
        self.dst_currency = Currencies.rls

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price')
    def test_get_mark_price_success(self, mock_mark_price):
        PriceProvider(self.src_currency, self.dst_currency).get_mark_price()
        mock_mark_price.assert_called_once_with(self.src_currency, self.dst_currency)

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', return_value=None)
    def test_get_mark_price_when_raises_exception(self, mock_mark_price):
        with pytest.raises(PriceNotAvailableError):
            PriceProvider(self.src_currency).get_mark_price()
        mock_mark_price.assert_called_once_with(self.src_currency, self.dst_currency)

    @patch('exchange.asset_backed_credit.externals.price.PriceEstimator.get_price_range')
    def test_get_nobitex_price_success(self, mock_price_range):
        mock_price_range.return_value = (0, 0)

        PriceProvider(self.src_currency, self.dst_currency).get_nobitex_price()
        mock_price_range.assert_called_once_with(self.src_currency, self.dst_currency)

    @patch('exchange.asset_backed_credit.externals.price.Market.get_for')
    def test_get_last_trade_price_success(self, mocked_get_for):
        PriceProvider(self.src_currency, self.dst_currency).get_last_trade_price()
        mocked_get_for.assert_called_once_with(self.src_currency, self.dst_currency)

    @responses.activate
    def test_get_nobitex_price_when_market_stats_api_is_enabled(self):
        responses.get(
            url=MarketStatAPI.url,
            json=self.market_stats_btc_rls_price,
            status=200,
        )
        Settings.set('abc_use_market_stats_api', 'yes')

        price = PriceProvider(self.src_currency, self.dst_currency).get_nobitex_price()
        assert price == Decimal(self.market_stats_btc_rls_price['stats']['btc-rls']['bestBuy'])

    @responses.activate
    def test_get_last_trade_price_success_when_market_stats_api_is_enabled(self):
        responses.get(
            url=MarketStatAPI.url,
            json=self.market_stats_btc_rls_price,
            status=200,
        )
        Settings.set('abc_use_market_stats_api', 'yes')

        price = PriceProvider(self.src_currency, self.dst_currency).get_last_trade_price()
        assert price == Decimal(self.market_stats_btc_rls_price['stats']['btc-rls']['latest'])

    @responses.activate
    def test_get_mark_price_success_when_market_stats_api_is_enabled(self):
        responses.get(
            url=MarketStatAPI.url,
            json=self.market_stats_btc_rls_price,
            status=200,
        )
        Settings.set('abc_use_market_stats_api', 'yes')

        price = PriceProvider(self.src_currency, self.dst_currency).get_mark_price()
        assert price == Decimal(self.market_stats_btc_rls_price['stats']['btc-rls']['mark'])

    @responses.activate
    def test_get_mark_price_success_when_market_stats_api_is_enabled_but_raises_error(self):
        responses.get(
            url=MarketStatAPI.url,
            json={},
            status=200,
        )
        Settings.set('abc_use_market_stats_api', 'yes')

        with pytest.raises(PriceNotAvailableError):
            PriceProvider(self.src_currency, self.dst_currency).get_mark_price()

    @responses.activate
    def test_get_last_trade_price_success_when_market_stats_api_is_enabled_but_raises_error(self):
        responses.get(
            url=MarketStatAPI.url,
            json={},
            status=200,
        )
        Settings.set('abc_use_market_stats_api', 'yes')

        with pytest.raises(PriceNotAvailableError):
            PriceProvider(self.src_currency, self.dst_currency).get_last_trade_price()

    @responses.activate
    def test_test_get_nobitex_price_when_market_stats_api_is_enabled_but_raises_error(self):
        responses.get(
            url=MarketStatAPI.url,
            json={},
            status=200,
        )
        Settings.set('abc_use_market_stats_api', 'yes')
        with pytest.raises(PriceNotAvailableError):
            PriceProvider(self.src_currency, self.dst_currency).get_nobitex_price()

    def test_get_nobitex_price_when_dst_currency_and_src_currency_are_same(self):
        price = PriceProvider(Currencies.btc, Currencies.btc).get_nobitex_price()
        assert price == Decimal(1)

    def test_get_mark_price_when_dst_currency_and_src_currency_are_same(self):
        price = PriceProvider(Currencies.rls, Currencies.rls).get_mark_price()
        assert price == Decimal(1)

    def test_get_last_trade_price_when_dst_currency_and_src_currency_are_same(self):
        price = PriceProvider(Currencies.usdt, Currencies.usdt).get_last_trade_price()
        assert price == Decimal(1)

    @responses.activate
    def test_get_mark_price_when_internal_api_is_enabled_with_success_response_but_do_not_have_mark_key_in_its_response(
        self,
    ):
        responses.get(
            url=MarketStatAPI.url,
            json=self.market_stats_btc_rls_price,
            status=200,
        )
        Settings.set('abc_use_market_stats_api', 'yes')

        with pytest.raises(PriceNotAvailableError):
            PriceProvider(self.src_currency, Currencies.usdt).get_nobitex_price()

    @patch('exchange.asset_backed_credit.externals.price.MarketStatAPI._request')
    def test_market_stats_when_all_abc_cache_has_not_current_pair_price_then_cache_is_ignored_and_api_is_called(
        self, mocked_request
    ):
        Settings.set('abc_use_market_stats_api', 'yes')
        mocked_request.return_value.json.side_effect = [
            self.market_stats_btc_rls_price,
            self.market_stats_btc_usdt_price,
        ]

        price = PriceProvider(self.src_currency, Currencies.usdt).get_nobitex_price()

        mocked_request.call_count = 2
        assert price == Decimal(self.market_stats_btc_usdt_price['stats']['btc-usdt']['bestBuy'])

    def tearDown(self):
        price_cache.clear()
