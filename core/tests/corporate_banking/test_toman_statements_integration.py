from datetime import datetime
from unittest.mock import patch

import requests
import responses
from django.test import TestCase

from exchange.corporate_banking.exceptions import ThirdPartyClientUnavailable
from exchange.corporate_banking.integrations.toman.statements import TomanBankStatementClient
from exchange.corporate_banking.models import ACCOUNT_TP, NOBITEX_BANK_CHOICES, CoBankAccount


class TestTomanBankStatementClient(TestCase):
    def setUp(self):
        self.from_time = datetime(2025, 1, 1, 0, 0, 0)
        self.to_time = datetime(2025, 1, 5, 23, 59, 59)
        self.bank_account = CoBankAccount.objects.create(
            provider_bank_id=4,
            bank=NOBITEX_BANK_CHOICES.saderat,
            iban='IR999999999999999999999991',
            account_number='111222333',
            account_tp=ACCOUNT_TP.operational,
        )
        self.cobank_client = TomanBankStatementClient(self.bank_account, self.from_time, self.to_time)
        self.successful_api_call = {
            'count': 12,
            'next': 'https://dbank-staging.qcluster.org/api/v1/account/12345/statement/?page=3&page_size=5',
            'previous': 'https://dbank-staging.qcluster.org/api/v1/account/12345/statement/?page_size=5',
            'results': [
                {
                    'id': 1234,
                    'amount': -213213,
                    'side': False,
                    'tracing_number': 'B0331231231649623307',
                    'transaction_datetime': '2055-01-05T03:33:13Z',
                    'created_at': '2025-01-05T02:37:22.414085Z',
                    'payment_id': None,
                    'source_account': None,
                    'balance': 1000000,
                    'branch_code': '815',
                },
                {
                    'id': 6892011,
                    'amount': 624100,
                    'side': True,
                    'tracing_number': 'B0310165010649622835',
                    'transaction_datetime': '2025-01-05T03:32:38Z',
                    'created_at': '2025-01-05T03:37:22.414121Z',
                    'is_normalized': False,
                    'source_account': '123456',
                },
                {
                    'id': 6892012,
                    'amount': -954400,
                    'side': False,
                    'tracing_number': 'B0310165010649622638',
                    'transaction_datetime': '2025-01-05T03:32:22Z',
                    'created_at': '2025-01-03T03:37:22.414156Z',
                    'is_normalized': False,
                    'payment_id': None,
                    'source_account': None,
                    'description': (
                        'انتقال وجه خدمات کاربر ثالث از ۸۱۵.7۱0-32۴4227-1 ش.پ 00001737561372345741'
                        ' - راهکارفناوري نويان-6411697194611395133'
                    ),
                },
                {
                    'id': 6892013,
                    'amount': 228600,
                    'side': True,
                    'tracing_number': 'B0310165010649622148',
                    'transaction_datetime': '2025-01-05T03:31:47Z',
                    'created_at': '2025-01-01T03:37:22.414192Z',
                    'is_normalized': False,
                    'payment_id': None,
                    'source_account': None,
                },
                {
                    'id': 6892014,
                    'amount': 1083600,
                    'side': True,
                    'tracing_number': 'B0310165010649618996',
                    'transaction_datetime': '2025-01-05T03:27:42Z',
                    'created_at': '2025-01-02T03:37:22.414226Z',
                    'is_normalized': False,
                    'payment_id': None,
                    'source_account': None,
                },
            ],
        }
        self.request_url = (
            f'https://dbank-staging.qcluster.org/api/v1/account/{self.bank_account.provider_bank_id}/statement/?'
            f'page=1&'
            f'page_size=50&'
            f'side=true&'
            f'created_at__gte={self.from_time.isoformat().replace(":", "%3A")}&'
            f'created_at__lte={self.to_time.isoformat().replace(":", "%3A")}'
        )

    @responses.activate
    @patch('exchange.corporate_banking.integrations.toman.base.Settings.get_value')
    def test_get_statements_success(self, mock_settings_get):
        """
        Test a successful call to get_statements.
        """
        mock_settings_get.return_value = 'fake-token-123'

        # First page response
        responses.add(responses.GET, self.request_url, json=self.successful_api_call, status=200)

        # Second (last) page response
        second_page_response = {
            'count': 12,
            'next': None,  # No next page
            'previous': 'https://dbank-staging.qcluster.org/api/v1/account/12345/statement/?page=1&page_size=5',
            'results': [
                {
                    'id': 6892015,
                    'amount': 550000,
                    'side': True,
                    'tracing_number': 'B0310165010649618997',
                    'transaction_datetime': '2025-01-05T03:30:42Z',
                    'created_at': '2025-01-04T03:37:22.414226Z',
                    'is_normalized': False,
                    'payment_id': None,
                    'source_account': None,
                },
            ],
        }
        second_page_url = self.request_url.replace('page=1', 'page=2')
        responses.add(responses.GET, second_page_url, json=second_page_response, status=200)

        all_statements = []
        for statements, page in self.cobank_client.get_statements(page_size=50):
            all_statements.extend(statements)

        assert len(all_statements) == 6

        expected_results = self.successful_api_call['results'] + second_page_response['results']
        for statement, expected_item in zip(all_statements, expected_results):
            assert statement.id == expected_item['id']
            assert statement.amount == expected_item['amount']
            assert statement.side == expected_item['side']
            assert statement.tracing_number == expected_item['tracing_number']
            assert statement.transaction_datetime == expected_item['transaction_datetime']
            assert statement.created_at == expected_item['created_at']
            assert statement.payment_id == expected_item.get('payment_id', None)
            assert statement.source_account == expected_item.get('source_account', None)
            assert statement.api_response == expected_item

        assert len(responses.calls) == 2
        assert 'Bearer fake-token-123' in responses.calls[0].request.headers.get('Authorization')
        assert 'Bearer fake-token-123' in responses.calls[1].request.headers.get('Authorization')

    @responses.activate
    @patch('exchange.corporate_banking.integrations.toman.base.Settings.get_value')
    @patch('exchange.corporate_banking.integrations.toman.base.CobankTomanAuthenticator.get_auth_token')
    def test_get_statements_no_access_token(self, mock_get_auth_token, mock_settings_get):
        """
        If no token is stored in Settings, the client should call CobankTomanAuthenticator.get_auth_token().
        """
        mock_settings_get.return_value = None
        mock_get_auth_token.return_value = 'new-token-xyz'

        responses.add(
            responses.GET,
            self.request_url,
            json={'count': 0, 'next': None, 'previous': None, 'results': []},
            status=200,
        )

        statements_pages = list(self.cobank_client.get_statements())

        # Since the response is empty, the generator should yield only one page with an empty list
        assert len(statements_pages) == 1
        statements, page = statements_pages[0]

        assert len(statements) == 0
        assert page == 1

        mock_get_auth_token.assert_called_once()
        assert len(responses.calls) == 1
        auth_header = responses.calls[0].request.headers.get('Authorization')
        assert 'Bearer new-token-xyz' in auth_header

    @responses.activate
    @patch('exchange.corporate_banking.integrations.toman.base.Settings.get_value')
    def test_get_statements_timeout_error(self, mock_settings_get):
        """
        If the request times out, the client should raise ThirdPartyClientUnavailable.
        """
        mock_settings_get.return_value = 'valid-token'
        responses.add(responses.GET, self.request_url, body=requests.Timeout('Connection timed out'))

        with self.assertRaises(ThirdPartyClientUnavailable) as ctx:
            list(self.cobank_client.get_statements())

        ex = ctx.exception
        assert 'Client Currently Unavailable: Connection timed out' in ex.message
        assert ex.code == 'Timeout'
        assert ex.status_code == -1  # Because e.response is None in a Timeout

        assert len(responses.calls) == 2  # Due to default retry, the request will be called twice in case of Timeout

    @responses.activate
    @patch('exchange.corporate_banking.integrations.toman.base.Settings.get_value')
    def test_get_statements_http_error(self, mock_settings_get):
        """
        If the server returns an HTTP error (e.g. 400 or 500), the client should raise ThirdPartyClientUnavailable.
        """
        mock_settings_get.return_value = 'valid-token'
        responses.add(responses.GET, self.request_url, json={'error': 'Bad Request'}, status=400)

        with self.assertRaises(ThirdPartyClientUnavailable) as ctx:
            for _ in self.cobank_client.get_statements():
                pass

        ex = ctx.exception
        assert 'Toman Client Currently Unavailable' in ex.message
        assert ex.code == 'HTTPError'
        assert ex.status_code == 400

        assert len(responses.calls) == 2

    @patch('exchange.corporate_banking.integrations.base.requests.request')
    @patch('exchange.corporate_banking.integrations.toman.base.Settings.get_value')
    def test_http_request_called_with_correct_args(self, mock_settings_get, mock_http_request):
        mock_settings_get.return_value = 'valid-token'

        # Mock response JSON
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response._content = b'{"count": 12, "next": null, "previous": null, "results": []}'

        mock_http_request.return_value = mock_response

        # Consume generator to trigger the request
        for _ in self.cobank_client.get_statements():
            break  # No need to loop fully, just testing request args

        mock_http_request.assert_called_once_with(
            'GET',
            self.request_url,
            headers={
                'Authorization': 'Bearer valid-token',
                'content-type': 'application/json',
            },
            data={},
            timeout=10,
        )
