from datetime import timedelta
from unittest.mock import MagicMock, patch

from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.base.serializers import serialize
from exchange.features.models import QueueItem
from exchange.xchange.models import MarketStatus
from exchange.xchange.status_collector import StatusCollector
from tests.xchange.helpers import MarketMakerStatusAPIMixin, update_exchange_side_configs
from tests.xchange.mocks import get_mock_exchange_side_config


class OptionsAPITest(APITestCase, MarketMakerStatusAPIMixin):
    def setUp(self) -> None:
        self.url = '/exchange/options'

    @patch('exchange.xchange.status_collector.time.sleep', new_callable=MagicMock)
    @patch('exchange.xchange.status_collector.Client.request', new_callable=MagicMock)
    def test_get_options_only_with_market_maker_api_statuses(self, mock_client_request, mock_sleep):
        self._assert_markets_unavailable_response(self.client.get(self.url))

        mock_client_request.return_value = self._get_mocked_response()
        status_collector = StatusCollector(12)
        status_collector._main_loop_method()

        response = self.client.get(self.url)
        self._assert_successful_api_call(
            response,
            expected_results=MarketStatus.objects.all(),
        )

    @patch('exchange.xchange.status_collector.time.sleep', new_callable=MagicMock)
    @patch('exchange.xchange.status_collector.Client.request', new_callable=MagicMock)
    def test_get_options_with_mixed_market_maker_api_statuses_and_admin_configs(self, mock_client_request, mock_sleep):
        mock_client_request.return_value = self._get_mocked_response()
        status_collector = StatusCollector(12)
        status_collector._main_loop_method()
        update_exchange_side_configs(get_mock_exchange_side_config())
        response = self.client.get(self.url)
        self._assert_successful_api_call(
            response,
            expected_results=MarketStatus.objects.all(),
        )

        mock_exchange_side_config = get_mock_exchange_side_config()
        mock_exchange_side_config[(Currencies.xrp, Currencies.usdt)] = MarketStatus.EXCHANGE_SIDE_CHOICES.closed
        update_exchange_side_configs(mock_exchange_side_config)
        response = self.client.get(self.url)
        self._assert_successful_api_call(
            response,
            expected_results=MarketStatus.objects.all(),
        )

        MarketStatus.objects.filter(base_currency=Currencies.near).update(
            status=MarketStatus.STATUS_CHOICES.unavailable,
        )
        response = self.client.get(self.url)
        self._assert_successful_api_call(
            response,
            expected_results=MarketStatus.objects.all(),
        )

    @patch('exchange.xchange.status_collector.time.sleep', new_callable=MagicMock)
    @patch('exchange.xchange.status_collector.Client.request', new_callable=MagicMock)
    def test_get_options_with_expired_market_maker_api_statuses(self, mock_client_request, mock_sleep):
        """
        Expiration don't effect results
        """
        mock_client_request.return_value = self._get_mocked_response()
        status_collector = StatusCollector(12)
        status_collector._main_loop_method()
        now = ir_now()
        before_expiration = now + timedelta(minutes=4)
        after_expiration = now + timedelta(minutes=6)
        with patch('exchange.xchange.models.ir_now', return_value=before_expiration):
            response = self.client.get(self.url)
            self._assert_successful_api_call(
                response,
                expected_results=MarketStatus.objects.all(),
            )
        with patch('exchange.xchange.models.ir_now', return_value=after_expiration):
            response = self.client.get(self.url)
            self._assert_successful_api_call(
                response,
                expected_results=MarketStatus.objects.all(),
            )

    @patch('exchange.xchange.status_collector.time.sleep', new_callable=MagicMock)
    @patch('exchange.xchange.status_collector.Client.request', new_callable=MagicMock)
    def test_get_options_with_delisted_pair(self, mock_client_request, mock_sleep):
        mock_client_request.return_value = self._get_mocked_response()
        status_collector = StatusCollector(12)
        status_collector._main_loop_method()

        MarketStatus.objects.filter(base_currency=Currencies.near).update(
            status=MarketStatus.STATUS_CHOICES.delisted,
        )

        response = self.client.get(self.url)
        self._assert_successful_api_call(
            response,
            expected_results=MarketStatus.objects.all(),
        )

    def _assert_successful_api_call(self, response, status_code=status.HTTP_200_OK, expected_results=[]):
        assert response.status_code == status_code
        json_response = response.json()
        assert 'status' in json_response
        assert json_response['status'] == 'ok'
        assert 'hasNext' not in json_response
        assert 'result' in json_response
        assert len(json_response['result']) == len(expected_results)
        for response, expected_result in zip(json_response['result'], expected_results):
            serialized_expected_result = serialize(expected_result)
            assert {
                'baseCurrency',
                'quoteCurrency',
                'baseToQuotePriceBuy',
                'quoteToBasePriceBuy',
                'baseToQuotePriceSell',
                'quoteToBasePriceSell',
                'minBaseAmount',
                'maxBaseAmount',
                'minQuoteAmount',
                'maxQuoteAmount',
                'basePrecision',
                'quotePrecision',
                'status',
                'updatedAt',
            }.issubset(response.keys())
            for key in serialized_expected_result:
                assert response[key] == serialized_expected_result[key]

    def _assert_markets_unavailable_response(self, response):
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'status': 'failed',
            'code': 'ConvertUnavailable',
            'message': 'Convert is not currently available.',
        }

    @patch('exchange.xchange.status_collector.time.sleep', new_callable=MagicMock)
    @patch('exchange.xchange.status_collector.Client.request', new_callable=MagicMock)
    @patch('exchange.xchange.models.XCHANGE_TESTING_CURRENCIES', new=[Currencies.sol])
    def test_check_beta_markets_feature_flag(self, mock_client_request, mock_sleep):
        user = User.objects.get(id=202)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {user.auth_token.key}'

        mock_client_request.return_value = self._get_mocked_response()
        status_collector = StatusCollector(12)
        status_collector._main_loop_method()

        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        result = response.json()['result']
        assert len(result) == 4
        assert 'sol' not in [currency['baseCurrency'] for currency in result]
        QueueItem.objects.create(feature=QueueItem.FEATURES.new_coins, user=user, status=QueueItem.STATUS.done)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        result = response.json()['result']
        assert len(result) == 5
        assert 'sol' in [currency['baseCurrency'] for currency in result]


class MarketOptionsAPITest(APITestCase, MarketMakerStatusAPIMixin):
    def setUp(self) -> None:
        self.url = '/exchange/options?market={market}'

    @patch('exchange.xchange.status_collector.time.sleep', new_callable=MagicMock)
    @patch('exchange.xchange.status_collector.Client.request', new_callable=MagicMock)
    def test_get_market_options_only_with_market_maker_api_statuses(self, mock_client_request, mock_sleep):
        self._assert_market_unavailable_response(self.client.get(self.url.format(market='NEARUSDT')))

        mock_client_request.return_value = self._get_mocked_response()
        status_collector = StatusCollector(12)
        status_collector._main_loop_method()
        response = self.client.get(self.url.format(market='NEARUSDT'))
        self._assert_successful_api_call(
            response,
            expected_result=MarketStatus.objects.get(base_currency=Currencies.near, quote_currency=Currencies.usdt),
        )

    def test_get_market_options_only_with_admin_configs(self):
        update_exchange_side_configs(get_mock_exchange_side_config())
        self._assert_market_unavailable_response(self.client.get(self.url.format(market='NEARUSDT')))

    @patch('exchange.xchange.status_collector.time.sleep', new_callable=MagicMock)
    @patch('exchange.xchange.status_collector.Client.request', new_callable=MagicMock)
    def test_get_market_options_with_mixed_market_maker_api_statuses_and_admin_configs(
        self,
        mock_client_request,
        mock_sleep,
    ):
        mock_client_request.return_value = self._get_mocked_response()
        status_collector = StatusCollector(12)
        status_collector._main_loop_method()
        update_exchange_side_configs(get_mock_exchange_side_config())
        response = self.client.get(self.url.format(market='SOLUSDT'))
        self._assert_successful_api_call(
            response,
            expected_result=MarketStatus.objects.get(base_currency=Currencies.sol, quote_currency=Currencies.usdt),
        )

        mock_exchange_side_config = get_mock_exchange_side_config()
        mock_exchange_side_config[(Currencies.sol, Currencies.usdt)] = MarketStatus.EXCHANGE_SIDE_CHOICES.closed
        update_exchange_side_configs(mock_exchange_side_config)
        response = self.client.get(self.url.format(market='SOLUSDT'))
        self._assert_successful_api_call(
            response,
            expected_result=MarketStatus.objects.get(base_currency=Currencies.sol, quote_currency=Currencies.usdt),
        )

    @patch('exchange.xchange.status_collector.time.sleep', new_callable=MagicMock)
    @patch('exchange.xchange.status_collector.Client.request', new_callable=MagicMock)
    def test_get_market_options_with_unavailable_market(
        self,
        mock_client_request,
        mock_sleep,
    ):
        mock_client_request.return_value = self._get_mocked_response()
        status_collector = StatusCollector(12)
        status_collector._main_loop_method()

        MarketStatus.objects.filter(base_currency=Currencies.sol).update(
            status=MarketStatus.STATUS_CHOICES.unavailable,
        )

        response = self.client.get(self.url.format(market='SOLUSDT'))
        self._assert_successful_api_call(
            response,
            expected_result=MarketStatus.objects.get(base_currency=Currencies.sol, quote_currency=Currencies.usdt),
        )

    @patch('exchange.xchange.status_collector.time.sleep', new_callable=MagicMock)
    @patch('exchange.xchange.status_collector.Client.request', new_callable=MagicMock)
    def test_get_market_options_with_expired_market_maker_api_statuses(self, mock_client_request, mock_sleep):
        """
        Expiration don't effect results
        """
        mock_client_request.return_value = self._get_mocked_response()
        status_collector = StatusCollector(12)
        status_collector._main_loop_method()
        now = ir_now()
        before_expiration = now + timedelta(minutes=4)
        after_expiration = now + timedelta(minutes=6)
        with patch('exchange.xchange.models.ir_now', return_value=before_expiration):
            response = self.client.get(self.url.format(market='SOLUSDT'))
            self._assert_successful_api_call(
                response,
                expected_result=MarketStatus.objects.get(base_currency=Currencies.sol, quote_currency=Currencies.usdt),
            )
        with patch('exchange.xchange.models.ir_now', return_value=after_expiration):
            self._assert_successful_api_call(
                response,
                expected_result=MarketStatus.objects.get(base_currency=Currencies.sol, quote_currency=Currencies.usdt),
            )

    @patch('exchange.xchange.status_collector.time.sleep', new_callable=MagicMock)
    @patch('exchange.xchange.status_collector.Client.request', new_callable=MagicMock)
    def test_get_market_options_with_delisted_pair(self, mock_client_request, mock_sleep):
        mock_client_request.return_value = self._get_mocked_response()
        status_collector = StatusCollector(12)
        status_collector._main_loop_method()

        MarketStatus.objects.filter(base_currency=Currencies.sol).update(
            status=MarketStatus.STATUS_CHOICES.delisted,
        )

        response = self.client.get(self.url.format(market='SOLUSDT'))
        self._assert_successful_api_call(
            response,
            expected_result=MarketStatus.objects.get(base_currency=Currencies.sol, quote_currency=Currencies.usdt),
        )

    def test_nonexistent_market(self):
        response = self.client.get(self.url.format(market='NONSENSEMARKET'))
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            'status': 'failed',
            'code': 'InvalidMarket',
            'message': 'Requested market does not exist.',
        }

    def _assert_successful_api_call(self, response, status_code=status.HTTP_200_OK, expected_result=None):
        assert response.status_code == status_code
        json_response = response.json()
        assert 'status' in json_response
        assert json_response['status'] == 'ok'
        assert 'result' in json_response
        if not expected_result:
            assert json_response['result'] is None
        else:
            serialized_expected_result = serialize(expected_result)
            assert {
                'baseCurrency',
                'quoteCurrency',
                'baseToQuotePriceBuy',
                'quoteToBasePriceBuy',
                'baseToQuotePriceSell',
                'quoteToBasePriceSell',
                'minBaseAmount',
                'maxBaseAmount',
                'minQuoteAmount',
                'maxQuoteAmount',
                'basePrecision',
                'quotePrecision',
                'status',
                'updatedAt',
            }.issubset(json_response['result'].keys())
            for key in serialized_expected_result:
                assert json_response['result'][key] == serialized_expected_result[key]

    def _assert_market_unavailable_response(self, response):
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'status': 'failed',
            'code': 'ConvertOnMarketUnavailable',
            'message': 'Convert on market is not currently available.',
        }

    @patch('exchange.xchange.status_collector.time.sleep', new_callable=MagicMock)
    @patch('exchange.xchange.status_collector.Client.request', new_callable=MagicMock)
    @patch('exchange.xchange.helpers.XCHANGE_TESTING_CURRENCIES', new=[Currencies.sol])
    def test_check_beta_markets_feature_flag(self, mock_client_request, mock_sleep):
        mock_client_request.return_value = self._get_mocked_response()
        status_collector = StatusCollector(12)
        status_collector._main_loop_method()

        response = self.client.get(self.url.format(market='SOLUSDT'))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'ConvertOnMarketUnavailable',
            'message': 'Convert on market is not currently available.',
            'status': 'failed',
        }

        user = User.objects.get(id=202)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {user.auth_token.key}'
        QueueItem.objects.create(feature=QueueItem.FEATURES.new_coins, user=user, status=QueueItem.STATUS.done)
        response = self.client.get(self.url.format(market='SOLUSDT'))
        assert response.status_code == status.HTTP_200_OK
