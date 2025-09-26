import urllib
from datetime import datetime, timezone
from unittest.mock import patch

import requests
import responses
from django.test import TestCase, override_settings

from exchange.corporate_banking.exceptions import ThirdPartyClientUnavailable
from exchange.corporate_banking.integrations.jibit.statements import JibitBankStatementClient
from exchange.corporate_banking.models import ACCOUNT_TP, NOBITEX_BANK_CHOICES, CoBankAccount


@override_settings(IS_TESTNET=False)
class TestJibitBankStatementClient(TestCase):
    def setUp(self):
        self.from_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        self.to_time = datetime(2025, 1, 5, 23, 59, 59, tzinfo=timezone.utc)
        self.bank_account = CoBankAccount.objects.create(
            provider_bank_id=4,
            bank=NOBITEX_BANK_CHOICES.saderat,
            iban='IR999999999999999999999991',
            account_number='111222333',
            account_tp=ACCOUNT_TP.operational,
        )
        self.cobank_client = JibitBankStatementClient(self.bank_account, self.from_time, self.to_time)
        self.successful_api_call = {
            'pageNumber': 1,
            'size': 10,
            'numberOfElements': 2,
            'hasNext': True,
            'hasPrevious': True,
            'elements': [
                {
                    'referenceNumber': 'string',
                    'accountIban': 'string',
                    'bankReferenceNumber': 'string',
                    'bankTransactionId': 'string',
                    'balance': 0,
                    'timestamp': '2025-02-15T10:03:43.492Z',
                    'creditAmount': 0,
                    'debitAmount': 0,
                    'rawData': 'string',
                    'sourceIdentifier': 'string',
                    'destinationIdentifier': 'string',
                    'sourceIban': 'string',
                    'destinationIban': 'string',
                    'sourceName': 'string',
                    'destinationName': 'string',
                    'payId': 'string',
                    'recordType': 'BARDASHT_UNKNOWN',
                    'merchantVerificationStatus': 'SYSTEM_REVIEW',
                    'kytStatus': 'NONE',
                    'refundType': 'FULL_REFUND',
                    'refundTrackId': 'string',
                    'createdAt': '2025-02-15T10:03:43.492Z',
                },
                {
                    'referenceNumber': '123',
                    'accountIban': 'IR220000000000000111111111',
                    'bankReferenceNumber': '2',
                    'bankTransactionId': '44',
                    'balance': 1,
                    'timestamp': '2024-03-21T17:21:39.492Z',
                    'creditAmount': 0,
                    'debitAmount': 10,
                    'rawData': 'string',
                    'sourceIdentifier': 'string',
                    'destinationIdentifier': 'string',
                    'sourceIban': 'string',
                    'destinationIban': 'string',
                    'sourceName': 'string',
                    'destinationName': 'string',
                    'recordType': 'BARDASHT_UNKNOWN',
                    'merchantVerificationStatus': 'SYSTEM_REVIEW',
                    'kytStatus': 'NONE',
                    'refundType': 'FULL_REFUND',
                    'refundTrackId': 'string',
                    'createdAt': '2025-02-15T10:03:43.492Z',
                },
            ],
            'metadata': {'additionalProp1': {}, 'additionalProp2': {}, 'additionalProp3': {}},
        }

        self.request_url = (
            f'https://napi.jibit.ir/cobank/v1/orders/aug-statement/{self.bank_account.iban}/variz/waitingForVerify?'
            f'createdAtFrom={urllib.parse.quote(self.from_time.isoformat(timespec="seconds").replace("+00:00", "Z"))}&'
            f'createdAtTo={urllib.parse.quote(self.to_time.isoformat(timespec="seconds").replace("+00:00", "Z"))}&'
            f'pageNumber=0&'
            f'pageSize=50'
        )

    @responses.activate
    @patch('exchange.corporate_banking.integrations.jibit.base.Settings.get_value')
    def test_get_statements_success(self, mock_settings_get_value):
        """
        Test a successful call to get_statements.
        """
        mock_settings_get_value.return_value = 'fake-token-123'

        responses.add(responses.GET, self.request_url, json=self.successful_api_call, status=200)

        statement_generator = self.cobank_client.get_statements(page_size=50)
        statements, page = next(statement_generator)

        assert len(statements) == 2
        assert page == 0
        assert statements[0].referenceNumber == 'string'


        for statement, expected_item in zip(statements, self.successful_api_call['elements']):
            assert statement.referenceNumber == expected_item['referenceNumber']
            assert statement.accountIban == expected_item['accountIban']
            assert statement.debitAmount == expected_item['debitAmount']
            assert statement.bankTransactionId == expected_item['bankTransactionId']
            assert statement.sourceIban == expected_item['sourceIban']
            assert statement.timestamp == expected_item['timestamp']
            assert statement.createdAt == expected_item['createdAt']
            assert statement.payId == expected_item.get('payId', None)
            assert statement.sourceIdentifier == expected_item['sourceIdentifier']
            assert statement.apiResponse == expected_item

        assert len(responses.calls) == 1
        assert 'Bearer fake-token-123' in responses.calls[0].request.headers.get('Authorization')

    @responses.activate
    @patch('exchange.corporate_banking.integrations.jibit.base.Settings.get_value')
    @patch('exchange.corporate_banking.integrations.jibit.authenticator.CobankJibitAuthenticator.get_auth_token')
    def test_get_statements_no_access_token(self, mock_get_auth_token, mock_settings_get_value):
        """
        If no token is stored in Settings, the client should call CobankJibitAuthenticator.get_auth_token().
        """
        mock_settings_get_value.return_value = None
        mock_get_auth_token.return_value = 'new-token-xyz'

        responses.add(
            responses.GET,
            self.request_url,
            json={
                'pageNumber': 0,
                'size': 0,
                'numberOfElements': 0,
                'hasNext': False,
                'hasPrevious': False,
                'elements': [],
            },
            status=200,
        )

        statement_generator = self.cobank_client.get_statements(page_size=50)
        next(statement_generator)

        mock_get_auth_token.assert_called_once()
        assert len(responses.calls) == 1
        auth_header = responses.calls[0].request.headers.get('Authorization')
        assert 'Bearer new-token-xyz' in auth_header

    @responses.activate
    @patch('exchange.corporate_banking.integrations.jibit.base.Settings.get_value')
    def test_get_statements_timeout_error(self, mock_settings_get_value):
        """
        If the request times out, the client should raise ThirdPartyClientUnavailable.
        """
        mock_settings_get_value.return_value = 'valid-token'
        responses.add(responses.GET, self.request_url, body=requests.Timeout('Connection timed out'))

        statement_generator = self.cobank_client.get_statements(page_size=50)
        with self.assertRaises(ThirdPartyClientUnavailable) as ctx:
            next(statement_generator)

        ex = ctx.exception
        assert 'Client Currently Unavailable: Connection timed out' in ex.message
        assert ex.code == 'Timeout'
        assert ex.status_code == -1  # Because e.response is None in a Timeout

        assert len(responses.calls) == 2  # Due to default retry, the request will be called twice in case of Timeout

    @responses.activate
    @patch('exchange.corporate_banking.integrations.jibit.base.Settings.get_value')
    def test_get_statements_http_error(self, mock_settings_get_value):
        """
        If the server returns an HTTP error (e.g. 400 or 500), the client should raise ThirdPartyClientUnavailable.
        """
        mock_settings_get_value.return_value = 'valid-token'
        responses.add(responses.GET, self.request_url, json={'error': 'Bad Request'}, status=400)

        statement_generator = self.cobank_client.get_statements(page_size=50)
        with self.assertRaises(ThirdPartyClientUnavailable) as ctx:
            next(statement_generator)

        ex = ctx.exception
        assert 'Jibit Client Currently Unavailable' in ex.message
        assert ex.code == 'HTTPError'
        assert ex.status_code == 400

        assert len(responses.calls) == 2

    @patch('exchange.corporate_banking.integrations.base.requests.request')
    @patch('exchange.corporate_banking.integrations.jibit.base.Settings.get_value')
    def test_http_request_called_with_correct_args(self, mock_settings_get_value, mock_http_request):
        mock_settings_get_value.return_value = 'valid-token'
        statement_generator = self.cobank_client.get_statements(page_size=50)
        next(statement_generator)

        mock_http_request.assert_called_once_with(
            'GET',
            self.request_url,
            headers={
                'Authorization': 'Bearer valid-token',
                'content-type': 'application/json',
            },
            json={},
            timeout=10,
        )
