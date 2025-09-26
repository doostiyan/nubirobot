from datetime import timedelta
from decimal import Decimal
from typing import List
from unittest.mock import patch

from django.test import TestCase

from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.base.serializers import serialize
from exchange.xchange.models import MarketStatus
from tests.xchange.helpers import update_exchange_side_configs, upsert_dict_as_currency_pair_status
from tests.xchange.mocks import (
    AVAX_USDT_STATUS,
    BAT_USDT_STATUS,
    NEAR_USDT_STATUS,
    SOL_USDT_STATUS,
    XRP_USDT_STATUS,
    get_mock_exchange_side_config,
)


class MarketStatusTest(TestCase):
    def setUp(self) -> None:
        upsert_dict_as_currency_pair_status(NEAR_USDT_STATUS)
        upsert_dict_as_currency_pair_status(SOL_USDT_STATUS)
        upsert_dict_as_currency_pair_status(XRP_USDT_STATUS)
        upsert_dict_as_currency_pair_status(AVAX_USDT_STATUS)
        upsert_dict_as_currency_pair_status(BAT_USDT_STATUS)

    def test_get_all_markets_statuses_with_default_configs(self):
        all_statuses = MarketStatus.get_all_markets_statuses()
        assert len(all_statuses) == 5
        self._assert_combination_of_statuses_and_configs(
            results=all_statuses,
            expectations=[NEAR_USDT_STATUS, SOL_USDT_STATUS, XRP_USDT_STATUS, AVAX_USDT_STATUS, BAT_USDT_STATUS],
        )

    def test_get_all_markets_statuses_with_no_statuses(self):
        MarketStatus.objects.all().delete()
        update_exchange_side_configs(get_mock_exchange_side_config())
        all_statuses = MarketStatus.get_all_markets_statuses()
        assert len(all_statuses) == 0
        self._assert_combination_of_statuses_and_configs(results=all_statuses, expectations=[])

    def test_get_all_markets_statuses(self):
        update_exchange_side_configs(get_mock_exchange_side_config())
        # There are 5 available statuses (near, sol, xrp, avax, bat)
        all_statuses = MarketStatus.get_all_markets_statuses()
        assert len(all_statuses) == 5
        self._assert_combination_of_statuses_and_configs(
            results=all_statuses,
            expectations=[NEAR_USDT_STATUS, SOL_USDT_STATUS, XRP_USDT_STATUS, AVAX_USDT_STATUS, BAT_USDT_STATUS],
        )

        MarketStatus.objects.filter(base_currency=Currencies.near).update(
            status=MarketStatus.STATUS_CHOICES.unavailable,
        )
        unavailable_near = dict(NEAR_USDT_STATUS)
        unavailable_near['status'] = 'unavailable'
        # There are 4 available statuses (sol, xrp, avax, bat) and 1 unavailable (near)
        all_statuses = MarketStatus.get_all_markets_statuses()
        assert len(all_statuses) == 5
        self._assert_combination_of_statuses_and_configs(
            results=all_statuses,
            expectations=[unavailable_near, SOL_USDT_STATUS, XRP_USDT_STATUS, AVAX_USDT_STATUS, BAT_USDT_STATUS],
        )

        mock_exchange_side_config = get_mock_exchange_side_config()
        mock_exchange_side_config[(Currencies.xrp, Currencies.usdt)] = MarketStatus.EXCHANGE_SIDE_CHOICES.closed
        update_exchange_side_configs(mock_exchange_side_config)
        # There are 4 available statuses (sol, xrp, avax, bat) and 1 unavailable (near)
        all_statuses = MarketStatus.get_all_markets_statuses()
        assert len(all_statuses) == 5
        self._assert_combination_of_statuses_and_configs(
            results=all_statuses,
            expectations=[unavailable_near, SOL_USDT_STATUS, XRP_USDT_STATUS, AVAX_USDT_STATUS, BAT_USDT_STATUS],
        )

    def test_get_all_markets_statuses_with_expired_statuses(self):
        """
        Expiration don't effect results
        """
        now = ir_now()
        before_expiration = now + timedelta(minutes=4)
        after_expiration = now + timedelta(minutes=6)
        with patch('exchange.xchange.models.ir_now', return_value=before_expiration):
            all_statuses = MarketStatus.get_all_markets_statuses()
            assert len(all_statuses) == 5
        with patch('exchange.xchange.models.ir_now', return_value=after_expiration):
            all_statuses = MarketStatus.get_all_markets_statuses()
            assert len(all_statuses) == 5

    def test_get_market_status_with_default_config(self):
        status = MarketStatus.get_market_status(base_currency=Currencies.near, quote_currency=Currencies.usdt)
        self._assert_market_status(
            result=status,
            expectation=NEAR_USDT_STATUS,
        )

    def test_get_market_status_with_no_status(self):
        MarketStatus.objects.filter(base_currency=Currencies.near).delete()
        update_exchange_side_configs(get_mock_exchange_side_config())
        status = MarketStatus.get_market_status(base_currency=Currencies.near, quote_currency=Currencies.usdt)
        assert status is None

    def test_get_market_status(self):
        update_exchange_side_configs(get_mock_exchange_side_config())

        status = MarketStatus.get_market_status(base_currency=Currencies.near, quote_currency=Currencies.usdt)
        self._assert_market_status(
            result=status,
            expectation=NEAR_USDT_STATUS,
        )

        MarketStatus.objects.filter(base_currency=Currencies.near).update(
            status=MarketStatus.STATUS_CHOICES.unavailable,
        )
        unavailable_near = dict(NEAR_USDT_STATUS)
        unavailable_near['status'] = 'unavailable'
        status = MarketStatus.get_market_status(base_currency=Currencies.near, quote_currency=Currencies.usdt)
        self._assert_market_status(
            result=status,
            expectation=unavailable_near,
        )

        mock_exchange_side_config = get_mock_exchange_side_config()
        mock_exchange_side_config[(Currencies.sol, Currencies.usdt)] = MarketStatus.EXCHANGE_SIDE_CHOICES.closed
        update_exchange_side_configs(mock_exchange_side_config)
        status = MarketStatus.get_market_status(base_currency=Currencies.sol, quote_currency=Currencies.usdt)
        self._assert_market_status(
            result=status,
            expectation=SOL_USDT_STATUS,
        )

    def test_get_market_status_with_expired_status(self):
        """
        Expiration don't effect results
        """
        now = ir_now()
        before_expiration = now + timedelta(minutes=4)
        after_expiration = now + timedelta(minutes=6)
        with patch('exchange.xchange.models.ir_now', return_value=before_expiration):
            status = MarketStatus.get_market_status(Currencies.xrp, Currencies.usdt)
            self._assert_market_status(
                result=status,
                expectation=XRP_USDT_STATUS,
            )
        with patch('exchange.xchange.models.ir_now', return_value=after_expiration):
            status = MarketStatus.get_market_status(Currencies.xrp, Currencies.usdt)
            self._assert_market_status(
                result=status,
                expectation=XRP_USDT_STATUS,
            )

    def test_get_market_status_with_is_sell_parameter(self):
        update_exchange_side_configs(get_mock_exchange_side_config())

        # sol market is a buy_only market, so it should be ok only with buy situation
        status = MarketStatus.get_available_market_status_based_on_side_filter(
            base_currency=Currencies.sol,
            quote_currency=Currencies.usdt,
            is_sell=False,
        )
        self._assert_market_status(
            result=status,
            expectation=SOL_USDT_STATUS,
        )

        status = MarketStatus.get_available_market_status_based_on_side_filter(
            base_currency=Currencies.sol,
            quote_currency=Currencies.usdt,
            is_sell=True,
        )
        assert status is None

        # xrp market is a sell_only market, so it should be ok only with sell situation
        status = MarketStatus.get_available_market_status_based_on_side_filter(
            base_currency=Currencies.xrp,
            quote_currency=Currencies.usdt,
            is_sell=True,
        )
        self._assert_market_status(
            result=status,
            expectation=XRP_USDT_STATUS,
        )

        status = MarketStatus.get_available_market_status_based_on_side_filter(
            base_currency=Currencies.xrp,
            quote_currency=Currencies.usdt,
            is_sell=False,
        )
        assert status is None

        # near market is a both_side market, so it should be ok with both sell & buy situations
        status = MarketStatus.get_available_market_status_based_on_side_filter(
            base_currency=Currencies.near,
            quote_currency=Currencies.usdt,
            is_sell=True,
        )
        self._assert_market_status(
            result=status,
            expectation=NEAR_USDT_STATUS,
        )

        status = MarketStatus.get_available_market_status_based_on_side_filter(
            base_currency=Currencies.near,
            quote_currency=Currencies.usdt,
            is_sell=False,
        )
        self._assert_market_status(
            result=status,
            expectation=NEAR_USDT_STATUS,
        )

        # bat market is a closed market, so it should not be ok with any situation
        status = MarketStatus.get_available_market_status_based_on_side_filter(
            base_currency=Currencies.bat,
            quote_currency=Currencies.usdt,
            is_sell=True,
        )
        assert status is None

        status = MarketStatus.get_available_market_status_based_on_side_filter(
            base_currency=Currencies.bat,
            quote_currency=Currencies.usdt,
            is_sell=False,
        )
        assert status is None

    def _assert_combination_of_statuses_and_configs(self, results: List[MarketStatus], expectations: List[dict]):
        for result in results:
            serialized_result = serialize(result)
            serialized_result[
                'status'
            ] = result.get_status_display()  # to handle the 'expired' status that is just for client
            for expectation in expectations:
                if (
                    serialized_result['baseCurrency'] == expectation['baseCurrency']
                    and serialized_result['quoteCurrency'] == expectation['quoteCurrency']
                ):
                    serialized_result.pop('updatedAt')
                    self._assert_equal_dicts(serialized_result, expectation)

    def _assert_market_status(self, result: MarketStatus, expectation: dict):
        serialized_result = serialize(result)
        serialized_result[
            'status'
        ] = result.get_status_display()  # to handle the 'expired' status that is just for client
        serialized_result.pop('updatedAt')
        self._assert_equal_dicts(serialized_result, expectation)

    def _assert_equal_dicts(self, actual: dict, expectation: dict):
        for key in expectation:
            assert key in actual
            if key in ('basePrecision', 'quotePrecision'):
                assert actual[key] == str(Decimal(f'1e{expectation[key]}'))
            elif key in ('baseCurrency', 'quoteCurrency', 'status'):
                assert actual[key].lower() == expectation[key]
            else:
                assert round(Decimal(actual[key]), 6) == round(Decimal(expectation[key]), 6)
