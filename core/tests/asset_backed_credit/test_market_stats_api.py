from unittest import TestCase
from unittest.mock import patch

import pytest
import responses

from exchange.asset_backed_credit.exceptions import FeatureUnavailable, InternalAPIError
from exchange.asset_backed_credit.externals.price import MarketStatAPI, price_cache
from exchange.base.models import Currencies, Settings, get_currency_codename


class MarketStatsAPITest(TestCase):
    def setUp(self):
        Settings.set('abc_use_market_stats_api', 'yes')

        self.market_stats_success_data = {
            "stats": {
                "btc-rls": {
                    "isClosed": False,
                    "bestSell": "37909910010",
                    "bestBuy": "37900000000",
                    "volumeSrc": "9.179418295725",
                    "volumeDst": "353844011098.226504216",
                    "latest": "37900000000",
                    "mark": "38030396280",
                    "dayLow": "37600100000",
                    "dayHigh": "39500000000",
                    "dayOpen": "39200000000",
                    "dayClose": "37900000000",
                    "dayChange": "-3.32",
                },
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
                "xtz-usdt": {
                    "isClosed": True,
                    "bestSell": "0",
                    "bestBuy": "0",
                    "volumeSrc": "0",
                    "volumeDst": "0",
                    "latest": "0",
                    "mark": "0",
                    "dayLow": "0",
                    "dayHigh": "0",
                    "dayOpen": "0",
                    "dayClose": "0",
                    "dayChange": "0",
                },
                "eth-rls": {
                    "isClosed": False,
                    "bestSell": "18784142850",
                    "bestBuy": "130000010",
                    "volumeSrc": "0.01415",
                    "volumeDst": "265795621.3275",
                    "latest": "18784142850",
                    "mark": "1572902560",
                    "dayLow": "18784142850",
                    "dayHigh": "18784142850",
                    "dayOpen": "18784142850",
                    "dayClose": "18784142850",
                    "dayChange": "0",
                },
                "pmn-rls": {"isClosed": True, "isClosedReason": "NoData"},
            },
            "global": {
                "binance": {
                    "c98": '0.1355',
                    "sfp": '0.731',
                    "1000xec": '0.03526',
                    "xem": '0.0193',
                    "zen": '8.213',
                    "omg": '0.2883',
                    "ata": '0.0923',
                    "iost": '0.0055',
                }
            },
        }
        self.filtered_currency_success_data = {
            "stats": {
                "usdt-rls": {
                    "isClosed": False,
                    "bestSell": "621480",
                    "bestBuy": "621400",
                    "volumeSrc": "940176.943391341285",
                    "volumeDst": "589255029645.2368047584",
                    "latest": "621480",
                    "mark": "621480",
                    "dayLow": "613430",
                    "dayHigh": "650000",
                    "dayOpen": "614020",
                    "dayClose": "621480",
                    "dayChange": "1.21",
                }
            },
            "global": {
                "binance": {"mkr": '1506.6', "srm": '0.287', "c98": '0.1244', "sfp": '0.6982', "1000xec": '0.0331'}
            },
        }

        self.src_currency, self.dst_currency = [get_currency_codename(Currencies.btc)], [
            get_currency_codename(Currencies.rls)
        ]

    @responses.activate
    def test_market_stats_successfully(self):
        responses.get(
            url=MarketStatAPI.url,
            json=self.market_stats_success_data,
            status=200,
        )
        market_schema = MarketStatAPI().request()
        assert market_schema.model_dump(mode='json', by_alias=True, exclude_none=True) == self.market_stats_success_data

    @responses.activate
    def test_market_stats_with_api_not_responding_correctly(self):
        responses.get(
            url=MarketStatAPI.url,
            json={'error': '<h1>Bad Request</h1>'},
            status=400,
        )
        with pytest.raises(InternalAPIError):
            MarketStatAPI().request()

    @responses.activate
    def test_market_stats_with_filtering_src_currency(self):
        responses.get(
            url=MarketStatAPI.url,
            json=self.filtered_currency_success_data,
            status=200,
        )
        market_schema = MarketStatAPI().request(self.src_currency)
        assert (
            market_schema.model_dump(mode='json', by_alias=True, exclude_none=True)
            == self.filtered_currency_success_data
        )

    @responses.activate
    def test_market_stats_with_filtering_dst_currency(self):
        responses.get(
            url=MarketStatAPI.url,
            json=self.filtered_currency_success_data,
            status=200,
        )
        market_schema = MarketStatAPI().request(dst_currencies=[get_currency_codename(Currencies.rls)])
        assert (
            market_schema.model_dump(mode='json', by_alias=True, exclude_none=True)
            == self.filtered_currency_success_data
        )

    @responses.activate
    def test_market_stats_with_filtering_both_src_currency_and_dst_currency(self):
        responses.get(
            url=MarketStatAPI.url,
            json=self.filtered_currency_success_data,
            status=200,
        )

        market_schema = MarketStatAPI().request(self.src_currency, self.dst_currency)
        assert (
            market_schema.model_dump(mode='json', by_alias=True, exclude_none=True)
            == self.filtered_currency_success_data
        )

    def test_with_feature_not_enabled_raises_exception(self):
        Settings.set('abc_use_market_stats_api', 'no')

        with pytest.raises(FeatureUnavailable):
            MarketStatAPI().request()

    @patch('exchange.asset_backed_credit.externals.price.MarketStatAPI._request')
    def test_calling_multiple_times_caches_in_the_first_call(self, mocked_request):
        mocked_request.return_value.json.return_value = self.market_stats_success_data

        MarketStatAPI().request(self.src_currency, self.dst_currency)
        MarketStatAPI().request(self.src_currency, self.dst_currency)

        mocked_request.assert_called_once()

    @patch('exchange.asset_backed_credit.externals.price.MarketStatAPI._request')
    def test_market_stats_caches_with_all_abc_currencies_when_cache_abc_currencies_is_used(self, mocked_request):
        mocked_request.return_value.json.return_value = self.market_stats_success_data

        market_api = MarketStatAPI(cache_abc_currencies=True)
        market_api.request(self.src_currency, self.dst_currency)
        market_api.request(self.src_currency, self.dst_currency)
        market_api.request(self.src_currency, self.dst_currency)

        mocked_request.assert_called_once()

    def tearDown(self):
        price_cache.clear()
