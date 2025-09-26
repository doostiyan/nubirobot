import functools
import signal
from datetime import timedelta
from decimal import Decimal
from unittest import mock
from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.test import TestCase
from django.utils import text

from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.xchange.constants import ALL_XCHANGE_PAIRS_CACHE_KEY
from exchange.xchange.exceptions import FailedFetchStatuses
from exchange.xchange.models import MarketStatus
from exchange.xchange.status_collector import StatusCollector
from tests.xchange.helpers import MarketMakerStatusAPIMixin
from tests.xchange.mocks import AVAX_USDT_STATUS, BAT_USDT_STATUS, NEAR_USDT_STATUS, SOL_USDT_STATUS, XRP_USDT_STATUS


def _patch_status_collector_initialization_internal_calls(test):
    @functools.wraps(test)
    @mock.patch.object(signal, 'signal', mock.Mock(return_value=None))
    def decorated(*args, **kwargs):
        return test(*args, **kwargs)

    return decorated


class StatusCollectorTest(TestCase, MarketMakerStatusAPIMixin):
    @mock.patch('exchange.xchange.status_collector.signal.signal')
    def test_initialization(self, signal_mock: mock.MagicMock):
        main_loop_sleep_period = 20
        status_collector = StatusCollector(main_loop_sleep_period)

        assert signal_mock.mock_calls == [
            mock.call(signal.SIGINT, status_collector.die),
            mock.call(signal.SIGTERM, status_collector.die),
        ]

    @_patch_status_collector_initialization_internal_calls
    def test_die(self):
        main_loop_sleep_period = 20
        status_collector = StatusCollector(main_loop_sleep_period)

        assert not status_collector.should_die
        status_collector.die()
        assert status_collector.should_die

    @mock.patch('exchange.xchange.status_collector.print', mock.MagicMock(return_value=None))
    @mock.patch('exchange.xchange.status_collector.time.sleep')
    @mock.patch.object(StatusCollector, 'fetch_statuses')
    @_patch_status_collector_initialization_internal_calls
    def test_main_loop_method(
        self,
        fetch_statuses: mock.MagicMock,
        sleep_mock: mock.MagicMock,
    ):
        fetch_statuses.return_value = self._get_mocked_status_pairs_response([('near', 'usdt'), ('sol', 'usdt')])[
            'result'
        ]
        status_collector = StatusCollector(12)
        status_collector._main_loop_method()
        fetch_statuses.assert_called_once()
        sleep_mock.assert_called_once_with(12)

        assert MarketStatus.objects.count() == 2
        self._assert_equal_statuses(MarketStatus.objects.get(base_currency=Currencies.near), NEAR_USDT_STATUS)
        self._assert_equal_statuses(MarketStatus.objects.get(base_currency=Currencies.sol), SOL_USDT_STATUS)

        fetch_statuses.return_value = self._get_mocked_status_pairs_response(
            [('near', 'usdt'), ('avax', 'usdt'), ('bat', 'usdt')]
        )['result']
        status_collector._main_loop_method()

        # Only two new items should have been inserted, near_usdt is just updated
        assert MarketStatus.objects.count() == 4
        self._assert_equal_statuses(MarketStatus.objects.get(base_currency=Currencies.near), NEAR_USDT_STATUS)
        self._assert_equal_statuses(MarketStatus.objects.get(base_currency=Currencies.sol), SOL_USDT_STATUS)
        self._assert_equal_statuses(MarketStatus.objects.get(base_currency=Currencies.bat), BAT_USDT_STATUS)
        self._assert_equal_statuses(MarketStatus.objects.get(base_currency=Currencies.avax), AVAX_USDT_STATUS)

    @mock.patch(
        'exchange.xchange.status_collector.XCHANGE_CURRENCIES', [Currencies.near, Currencies.avax, Currencies.bat]
    )
    @mock.patch('exchange.xchange.status_collector.print', mock.MagicMock(return_value=None))
    @mock.patch('exchange.xchange.status_collector.time.sleep')
    @mock.patch.object(StatusCollector, 'fetch_statuses')
    @_patch_status_collector_initialization_internal_calls
    def test_cache_all_currency_pairs(self, fetch_statuses: mock.MagicMock, sleep_mock: mock.MagicMock):
        # In each iteration of the main loop we cache all the pairs of currencies ever available only in xchange,
        #  whether older than the MarketStatus's EXPIRATION_TIME_IN_MINUTES or not
        status_collector = StatusCollector(12)
        fetch_statuses.return_value = self._get_mocked_status_pairs_response([('near', 'usdt')])['result']
        status_collector._main_loop_method()
        assert cache.get(ALL_XCHANGE_PAIRS_CACHE_KEY) == [
            (Currencies.near, Currencies.usdt),
            (Currencies.usdt, Currencies.near),
        ]

        MarketStatus.objects.filter(base_currency=Currencies.near).update(created_at=ir_now() - timedelta(minutes=6))
        fetch_statuses.return_value = self._get_mocked_status_pairs_response([('avax', 'usdt'), ('bat', 'usdt')])[
            'result'
        ]
        status_collector._main_loop_method()
        assert cache.get(ALL_XCHANGE_PAIRS_CACHE_KEY) == [
            (Currencies.near, Currencies.usdt),
            (Currencies.usdt, Currencies.near),
            (Currencies.avax, Currencies.usdt),
            (Currencies.usdt, Currencies.avax),
            (Currencies.bat, Currencies.usdt),
            (Currencies.usdt, Currencies.bat),
        ]

        with mock.patch('exchange.xchange.status_collector.XCHANGE_CURRENCIES', [Currencies.bat]):
            status_collector._main_loop_method()
        assert cache.get(ALL_XCHANGE_PAIRS_CACHE_KEY) == [
            (Currencies.bat, Currencies.usdt),
            (Currencies.usdt, Currencies.bat),
        ]

    @patch('exchange.xchange.status_collector.Client.request', new_callable=MagicMock)
    def test_call_fetch_statuses_successfully(self, mock_client_request):
        mock_client_request.return_value = self._get_mocked_response()
        status_collector = StatusCollector(12)
        statuses = status_collector.fetch_statuses()
        statuses.sort(key=lambda item: item['baseCurrency'])
        assert statuses == [AVAX_USDT_STATUS, BAT_USDT_STATUS, NEAR_USDT_STATUS, SOL_USDT_STATUS, XRP_USDT_STATUS]

    @patch('exchange.xchange.status_collector.Client.request', new_callable=MagicMock)
    def test_get_failed_response(self, mock_client_request):
        mock_client_request.side_effect = requests.HTTPError
        status_collector = StatusCollector(12)
        with self.assertRaises(FailedFetchStatuses):
            status_collector.fetch_statuses()

    @patch('exchange.xchange.status_collector.Client.request', new_callable=MagicMock)
    def test_get_timed_out_response(self, mock_client_request):
        mock_client_request.return_value = self._get_mocked_response(hasError='True')
        status_collector = StatusCollector(12)
        with self.assertRaises(FailedFetchStatuses):
            status_collector.fetch_statuses()

    @mock.patch('exchange.xchange.status_collector.time.sleep', new_callable=MagicMock)
    @mock.patch.object(StatusCollector, 'fetch_statuses')
    def test_upsert(
        self,
        fetch_statuses: mock.MagicMock,
        mock_sleep: mock.MagicMock,
    ):
        fetch_statuses.return_value = self._get_mocked_status_pairs_response([('near', 'usdt'), ('sol', 'usdt')])[
            'result'
        ]
        status_collector = StatusCollector(12)
        status_collector._main_loop_method()
        near_usdt_status_before_update = MarketStatus.objects.get(base_currency=Currencies.near)
        sol_usdt_status_before_update = MarketStatus.objects.get(base_currency=Currencies.sol)

        fetch_statuses.return_value = self._get_mocked_status_pairs_response([('near', 'usdt')])['result']
        status_collector._main_loop_method()
        near_usdt_status_after_update = MarketStatus.objects.get(base_currency=Currencies.near)
        sol_usdt_status_after_update = MarketStatus.objects.get(base_currency=Currencies.sol)
        assert near_usdt_status_after_update.created_at == near_usdt_status_before_update.created_at
        assert near_usdt_status_after_update.updated_at > near_usdt_status_before_update.updated_at
        assert sol_usdt_status_after_update.created_at == sol_usdt_status_before_update.created_at
        assert sol_usdt_status_after_update.updated_at == sol_usdt_status_after_update.updated_at

    @mock.patch('exchange.xchange.status_collector.time.sleep', new_callable=MagicMock)
    @mock.patch.object(StatusCollector, 'fetch_statuses')
    def test_bypass_delisted_market(
        self,
        fetch_statuses: mock.MagicMock,
        mock_sleep: mock.MagicMock,
    ):
        fetch_statuses.return_value = self._get_mocked_status_pairs_response([('near', 'usdt'), ('sol', 'usdt')])[
            'result'
        ]
        status_collector = StatusCollector(12)
        status_collector._main_loop_method()
        near_usdt_status_before_update = MarketStatus.objects.get(base_currency=Currencies.near)
        sol_usdt_status_before_update = MarketStatus.objects.get(base_currency=Currencies.sol)
        sol_usdt_status_before_update.status = MarketStatus.STATUS_CHOICES.delisted
        sol_usdt_status_before_update.save()

        fetch_statuses.return_value = self._get_mocked_status_pairs_response([('near', 'usdt'), ('sol', 'usdt')])[
            'result'
        ]
        status_collector._main_loop_method()
        near_usdt_status_after_update = MarketStatus.objects.get(base_currency=Currencies.near)
        sol_usdt_status_after_update = MarketStatus.objects.get(base_currency=Currencies.sol)

        assert near_usdt_status_after_update.created_at == near_usdt_status_before_update.created_at
        assert near_usdt_status_after_update.updated_at > near_usdt_status_before_update.updated_at

        assert sol_usdt_status_after_update.created_at == sol_usdt_status_before_update.created_at
        assert sol_usdt_status_after_update.updated_at == sol_usdt_status_after_update.updated_at
        assert sol_usdt_status_after_update.status == MarketStatus.STATUS_CHOICES.delisted

    @mock.patch('exchange.xchange.helpers.to_shamsi_date', return_value='1403/10/04 11:08:22')
    @mock.patch('exchange.xchange.helpers.Notification.notify_admins')
    @mock.patch('exchange.xchange.status_collector.time.sleep', new_callable=MagicMock)
    @mock.patch.object(StatusCollector, 'fetch_statuses')
    def test_call_notify_admin_when_status_was_changed(
        self, fetch_statuses: mock.MagicMock, mock_sleep: mock.MagicMock, notify_admin_mock, shamsi_date_mock
    ):

        fetch_statuses.return_value = self._get_mocked_status_pairs_response([('near', 'usdt'), ('sol', 'usdt')])[
            'result'
        ]
        status_collector = StatusCollector(12)
        status_collector._main_loop_method()
        notify_admin_mock.assert_not_called()
        MarketStatus.objects.filter(base_currency=Currencies.near).update(
            status=MarketStatus.STATUS_CHOICES.unavailable
        )
        MarketStatus.objects.filter(base_currency=Currencies.sol).update(status=MarketStatus.STATUS_CHOICES.unavailable)

        status_collector._main_loop_method()
        notify_admin_mock.assert_called_once_with(
            message='تغییر وضعیت بازارها در 1403/10/04 11:08:22 : \nNEARUSDT: Unavailable -> Available\nSOLUSDT: Unavailable -> Available\n',
            title='هشدار تغییر وضعیت بازارها 🔔',
            channel='important_xchange',
        )

    @classmethod
    def _assert_equal_statuses(cls, pair_status_model: MarketStatus, pair_status_dict: dict):
        pair_status_dict = {
            text.camel_case_to_spaces(key).replace(' ', '_'): pair_status_dict[key] for key in pair_status_dict
        }
        assert pair_status_model.base_currency == getattr(Currencies, pair_status_dict['base_currency'])
        assert pair_status_model.quote_currency == getattr(Currencies, pair_status_dict['quote_currency'])
        assert round(pair_status_model.base_to_quote_price_buy, 6) == round(
            Decimal(pair_status_dict['base_to_quote_price_buy']), 6
        )
        assert round(pair_status_model.quote_to_base_price_buy, 6) == round(
            Decimal(pair_status_dict['quote_to_base_price_buy']), 6
        )
        assert round(pair_status_model.base_to_quote_price_sell, 6) == round(
            Decimal(pair_status_dict['base_to_quote_price_sell']), 6
        )
        assert round(pair_status_model.quote_to_base_price_sell, 6) == round(
            Decimal(pair_status_dict['quote_to_base_price_sell']), 6
        )
        assert round(pair_status_model.min_base_amount, 6) == round(Decimal(pair_status_dict['min_base_amount']), 6)
        assert round(pair_status_model.max_base_amount, 6) == round(Decimal(pair_status_dict['max_base_amount']), 6)
        assert round(pair_status_model.min_quote_amount, 6) == round(Decimal(pair_status_dict['min_quote_amount']), 6)
        assert round(pair_status_model.max_quote_amount, 6) == round(Decimal(pair_status_dict['max_quote_amount']), 6)
        assert pair_status_model.base_precision == Decimal(f'1e{pair_status_dict["base_precision"]}')
        assert pair_status_model.quote_precision == Decimal(f'1e{pair_status_dict["quote_precision"]}')
        assert pair_status_model.status == MarketStatus.STATUS_CHOICES._identifier_map.get(pair_status_dict['status'])
