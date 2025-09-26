import unittest
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from requests import HTTPError

from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.xchange.exceptions import QuoteIsNotAvailable
from exchange.xchange.marketmaker.client import Client
from exchange.xchange.marketmaker.quotes import Estimator

MOCK_SUCCESSFUL_CALL = {
    'result': {
        'quoteId': 'Q00001',
        'referenceCurrencyRealAmount': 0.1,
        'destinationCurrencyAmount': 4421.51,
        'baseCurrency': 'btc',
        'quoteCurrency': 'usdt',
        'clientId': 'clid_00000001',
        'creationTime': 1702451151,
        'validationTTL': 10000,
        'side': 'sell',
        'referenceCurrency': 'btc',
        'referenceCurrencyOriginalAmount': 0.00001,
    },
    'message': 'successful message',
    'error': 'success',
    'hasError': False,
}


class EstimatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.params = {
            'base_currency': Currencies.btc,
            'quote_currency': Currencies.usdt,
            'is_sell': True,
            'reference_currency': Currencies.btc,
            'amount': Decimal(0.1),
            'user_id': 201,
        }

    def setUp(self) -> None:
        cache.delete(Estimator.CACHE_KEY_TEMPLATE.format(quote_id='Q00001', user_id=201))

    @patch('exchange.xchange.marketmaker.quotes.uuid.uuid4')
    @patch('exchange.xchange.marketmaker.quotes.Client.request')
    def test_get_called_with_correct_params(self, mock_post, mock_uuid4):
        mock_post.return_value = self._get_mocked_response(result={'creationTime': ir_now().timestamp() * 1000})
        mock_id = uuid.UUID('a' * 32)
        mock_uuid4.return_value = mock_id
        Estimator.estimate(**self.params)
        mock_post.assert_called_once_with(
            Client.Method.POST,
            '/xconvert/estimate',
            {
                'clientId': mock_id.hex,
                'baseCurrency': 'btc',
                'quoteCurrency': 'usdt',
                'side': 'sell' if self.params['is_sell'] else 'buy',
                'referenceCurrency': 'btc',
                'referenceCurrencyAmount': str(self.params['amount']),
            },
        )

    @patch('exchange.xchange.marketmaker.quotes.Client.request')
    def test_estimate_and_set_cache_successfully(self, mock_post):
        mock_post.return_value = self._get_mocked_response(result={'creationTime': ir_now().timestamp() * 1000})
        quote = Estimator.estimate(**self.params)
        cached_quote = Estimator.get_quote('Q00001', 201)
        assert quote.quote_id == cached_quote.quote_id == 'Q00001'
        assert quote.base_currency == cached_quote.base_currency == Currencies.btc
        assert quote.quote_currency == cached_quote.quote_currency == Currencies.usdt
        assert quote.reference_currency == cached_quote.reference_currency == Currencies.btc
        assert quote.reference_amount == cached_quote.reference_amount == Decimal(0.1)
        assert quote.destination_amount == cached_quote.destination_amount == Decimal(4421.51)
        assert quote.is_sell == cached_quote.is_sell == True
        assert quote.client_order_id == cached_quote.client_order_id
        assert quote.expires_at == cached_quote.expires_at
        assert quote.user_id == cached_quote.user_id == 201

    @patch('exchange.xchange.marketmaker.quotes.Client.request', new_callable=MagicMock)
    def test_quote_expiration(self, mock_post):
        now = ir_now()
        mock_post.return_value = self._get_mocked_response(result={'creationTime': now.timestamp() * 1000})
        quote = Estimator.estimate(**self.params)
        before_expiration = now + timedelta(seconds=9)
        after_expiration = now + timedelta(seconds=11)
        with patch('exchange.xchange.marketmaker.quotes.ir_now', return_value=before_expiration):
            cached_quote = Estimator.get_quote('Q00001', 201)
            assert quote == cached_quote
        with patch('exchange.xchange.marketmaker.quotes.ir_now', return_value=after_expiration):
            with self.assertRaises(QuoteIsNotAvailable):
                Estimator.get_quote('Q00001', 201)

    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(side_effect=HTTPError))
    def test_get_failed_response(self):
        with self.assertRaises(HTTPError):
            Estimator.estimate(**self.params)
        with self.assertRaises(QuoteIsNotAvailable):
            Estimator.get_quote(quote_id='Q00001', user_id=201)

    def _get_mocked_response(self, **kwargs) -> dict:
        mock_response = MOCK_SUCCESSFUL_CALL
        if 'result' in kwargs:
            if isinstance(kwargs['result'], dict):
                mock_response['result'].update(kwargs['result'])
            elif isinstance(kwargs['result'], str):
                mock_response['result'] = kwargs['result']
        mock_response['message'] = kwargs.get('message') or mock_response['message']
        mock_response['error'] = kwargs.get('error') or mock_response['error']
        mock_response['hasError'] = kwargs.get('hasError') or mock_response['hasError']
        return mock_response
