from unittest.mock import patch

from django.core.cache import cache
from rest_framework.test import APITestCase

from exchange.base.models import Settings
from tests.market.test_order import OrderAPITestMixin


class MarketMakerSentryTestCase(OrderAPITestMixin, APITestCase):
    MARKET_SYMBOL = 'BTCUSDT'

    def setUp(self):
        super().setUp()
        Settings.set('marketmaker_sentry_transactions_capture_sample_rate', '1')

    def tearDown(self):
        cache.clear()

    def get_request_body(self):
        body = {
            'type': 'sell',
            'execution': 'limit',
            'srcCurrency': 'BTC',
            'dstCurrency': 'USDT',
            'amount': '10000',
            'price': '10000',
            'clientOrderId': 'blahblahbsajdhasd',
        }

        return body

    @patch('exchange.market.decorators.sentry_sdk.start_transaction')
    def test_transaction_sampled_successfully_for_marketmaker(self, mocked_sentry):
        with self.settings(TRADER_BOT_IDS=[self.user.id]):
            self.client.post('/market/orders/add', data=self.get_request_body())

        mocked_sentry.assert_called()

    @patch('exchange.market.decorators.sentry_sdk.start_transaction')
    def test_transaction_passed_for_non_marketmaker_users(self, mocked_sentry):
        with self.settings(TRADER_BOT_IDS=[]):
            self.client.post('/market/orders/add', data=self.get_request_body())

        mocked_sentry.assert_not_called()

    @patch('exchange.market.decorators.sentry_sdk.start_transaction')
    def test_transaction_passed_for_0_sample_rate(self, mocked_sentry):
        Settings.set('marketmaker_sentry_transactions_capture_sample_rate', '0')

        with self.settings(TRADER_BOT_IDS=[self.user.id]):
            self.client.post('/market/orders/add', data=self.get_request_body())

        mocked_sentry.assert_not_called()
