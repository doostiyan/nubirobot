import contextlib
from decimal import Decimal
from unittest.mock import Mock, patch

import requests
import responses
from django.conf import settings
from django.test import TestCase, override_settings

from exchange.base.models import Settings
from exchange.corporate_banking.integrations.toman.refund import RefundStatementTomanClient
from exchange.corporate_banking.models import (
    ACCOUNT_TP,
    NOBITEX_BANK_CHOICES,
    REFUND_STATUS,
    STATEMENT_STATUS,
    STATEMENT_TYPE,
    CoBankAccount,
    CoBankRefund,
    CoBankStatement,
)
from tests.corporate_banking.test_toman_authenticator import CobankTomanAuthenticator


class TestRefundStatementTomanClientAPI(TestCase):
    def setUp(self):
        self.bank_account = CoBankAccount.objects.create(
            provider_bank_id=123,
            bank=NOBITEX_BANK_CHOICES.saman,
            iban='IR999999999999999999999991',
            account_number='10.8593617.1',
            account_owner='راهکار فناوری نویان',
            is_active=True,
            account_tp=ACCOUNT_TP.operational,
            is_deleted=False,
        )
        self.statement = CoBankStatement.objects.create(
            amount=Decimal('10000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRC-001',
            transaction_datetime='2025-01-05T03:33:13Z',
            destination_account=self.bank_account,
            status=STATEMENT_STATUS.rejected,
            source_account='SRC.9876',
            provider_statement_id=456,
        )
        self.refund_request = CoBankRefund.objects.create(
            statement=self.statement,
            status=REFUND_STATUS.new,
        )
        self.sample_toman_response = {
            'id': 1,
            'transfer': {
                'uuid': 'a524ffb9-34c3-4903-be9b-e82ec922b45f',
                'bank_id': 15,
                'account': 84,
                'account_number_source': '826-810-4704696-2',
                'iban_source': 'IR300560082681004704696002',
                'transfer_type': 0,
                'status': 14,
                'amount': 1100,
                'iban_destination': 'IR300560082681004704696002',
                'account_number_destination': '826-810-4704696-2',
                'card_number_destination': None,
                'description': None,
                'first_name': None,
                'last_name': None,
                'reason': 6,
                'tracker_id': 'c1c995ef-fc23-4656-aa13-e25996326f9b',
                'created_at': '2025-03-12T10:54:54.231888Z',
                'created_by': 60,
                'creation_type': 20,
                'bank_id_destination': 15,
                'follow_up_code': None,
                'payment_id': None,
                'receipt_link': 'https://settlement.toman.ir/receipt/cb/a524ffb9-34c3-4903-be9b-e82ec922b45f:'
                '9ead9200dcfc2e0701be67b5cfd7b3d489c1fb6fd59f8ae29f073d3ee7c29a35',
                'attachment_count': 0,
                'attachments': [],
            },
            'statement_id': 941,
            'created_at': '2025-04-26T01:24:56.801425Z',
            'updated_at': '2025-04-26T01:24:56.801442Z',
            'status': 0,
            'account': 1,
            'created_by': 60,
            'partner': 1,
        }
        Settings.set('cobank_toman_access_token', 'some_access_token')

    @override_settings(IS_PROD=True)
    @patch.object(RefundStatementTomanClient, '_send_refund_request')
    def test_refund_statement_api_url_prod(self, mock_send_request):
        refund_client = RefundStatementTomanClient()
        mock_send_request.return_value = Mock()
        assert settings.IS_PROD is True
        refund_client.refund_statement(self.refund_request)

        expected_api_url = '/revert/'
        assert refund_client.api_url == expected_api_url

        expected_full_url = 'https://dbank.toman.ir/api/v1/revert/'
        actual_full_url = refund_client.get_request_url()
        assert actual_full_url == expected_full_url

    @override_settings(IS_PROD=False)
    @patch.object(RefundStatementTomanClient, '_send_refund_request')
    def test_refund_statement_api_url_staging(self, mock_send_request):
        refund_client = RefundStatementTomanClient()
        mock_send_request.return_value = Mock()

        refund_client.refund_statement(self.refund_request)

        expected_api_url = '/revert/'
        assert refund_client.api_url == expected_api_url

        expected_full_url = 'https://dbank-staging.qcluster.org/api/v1/revert/'
        actual_full_url = refund_client.get_request_url()
        assert actual_full_url == expected_full_url

    @override_settings(IS_PROD=True)
    @patch.object(RefundStatementTomanClient, '_send_refund_request')
    def test_check_refund_status_api_url_prod(self, mock_send_request):
        refund_client = RefundStatementTomanClient()
        mock_send_request.return_value = Mock()
        assert settings.IS_PROD is True

        refund_client.api_url = '/revert'
        refund_client.check_refund_status(self.refund_request)

        expected_api_url = '/revert/123/456/'
        assert refund_client.api_url == expected_api_url

        expected_full_url = 'https://dbank.toman.ir/api/v1/revert/123/456/'
        actual_full_url = refund_client.get_request_url()
        assert actual_full_url == expected_full_url

    @override_settings(IS_PROD=False)
    @patch.object(RefundStatementTomanClient, '_send_refund_request')
    def test_check_refund_status_api_url_staging(self, mock_send_request):
        refund_client = RefundStatementTomanClient()
        mock_send_request.return_value = Mock()

        refund_client.api_url = '/revert'
        refund_client.check_refund_status(self.refund_request)

        expected_api_url = '/revert/123/456/'
        assert refund_client.api_url == expected_api_url

        expected_full_url = 'https://dbank-staging.qcluster.org/api/v1/revert/123/456/'
        actual_full_url = refund_client.get_request_url()
        assert actual_full_url == expected_full_url

    @override_settings(IS_PROD=False)
    def test_get_request_url_with_custom_api_url(self):
        refund_client = RefundStatementTomanClient()
        custom_api_url = '/custom/endpoint'
        expected_full_url = 'https://dbank-staging.qcluster.org/api/v1/custom/endpoint'
        actual_full_url = refund_client.get_request_url(custom_api_url)

        assert actual_full_url == expected_full_url

    @override_settings(IS_PROD=False)
    def test_get_request_url_with_default_api_url(self):
        refund_client = RefundStatementTomanClient()
        refund_client.api_url = '/default/endpoint'

        expected_full_url = 'https://dbank-staging.qcluster.org/api/v1/default/endpoint'
        actual_full_url = refund_client.get_request_url()

        assert actual_full_url == expected_full_url

    @override_settings(IS_PROD=False)
    @patch.object(RefundStatementTomanClient, '_send_refund_request')
    def test_api_url_state_between_methods(self, mock_send_request):
        refund_client = RefundStatementTomanClient()
        mock_send_request.return_value = Mock()

        refund_client.api_url = '/revert'
        refund_client.refund_statement(self.refund_request)
        refund_statement_url = refund_client.api_url

        refund_client.api_url = '/revert'
        refund_client.check_refund_status(self.refund_request)
        check_status_url = refund_client.api_url

        assert refund_statement_url == '/revert/'
        assert check_status_url == '/revert/123/456/'
        assert refund_statement_url != check_status_url

    @override_settings(IS_PROD=False)
    @patch.object(RefundStatementTomanClient, '_send_refund_request')
    def test_payload_content_for_refund_statement(self, mock_send_request):
        refund_client = RefundStatementTomanClient()
        mock_send_request.return_value = Mock()

        refund_client.refund_statement(self.refund_request)

        expected_payload = {
            'account': 123,
            'statement_id': 456,
        }
        assert refund_client.payload == expected_payload
        assert refund_client.request_method == 'POST'

    @override_settings(IS_PROD=False)
    @patch.object(RefundStatementTomanClient, '_send_refund_request')
    def test_request_method_for_check_refund_status(self, mock_send_request):
        refund_client = RefundStatementTomanClient()
        mock_send_request.return_value = Mock()

        refund_client.check_refund_status(self.refund_request)

        assert refund_client.request_method == 'GET'

    @patch('requests.request')
    def test_is_json_parameter_in_refund_statement_request(self, mock_request):
        mock_response = Mock()
        mock_response.json.return_value = self.sample_toman_response
        mock_request.return_value = mock_response

        refund_client = RefundStatementTomanClient()
        refund_client.refund_statement(self.refund_request)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert 'json' in call_args[1]
        assert 'data' not in call_args[1]
        assert call_args[1]['json'] == {
            'account': 123,
            'statement_id': 456,
        }

    @patch('requests.request')
    def test_is_json_parameter_in_check_refund_status_request(self, mock_request):
        mock_response = Mock()
        mock_response.json.return_value = self.sample_toman_response
        mock_request.return_value = mock_response

        refund_client = RefundStatementTomanClient()
        refund_client.check_refund_status(self.refund_request)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert 'json' in call_args[1]
        assert 'data' not in call_args[1]
        assert call_args[1]['json'] == {}

    @patch('requests.request')
    def test_is_json_parameter_in_retry_scenario(self, mock_request):
        mock_response_success = Mock()
        mock_response_success.json.return_value = self.sample_toman_response

        mock_request.side_effect = [
            requests.HTTPError('Connection failed'),
            mock_response_success,
        ]

        refund_client = RefundStatementTomanClient()
        refund_client.refund_statement(self.refund_request)

        assert mock_request.call_count == 2

        first_call_args = mock_request.call_args_list[0]
        assert 'json' in first_call_args[1]
        assert 'data' not in first_call_args[1]
        assert first_call_args[1]['json'] == {
            'account': 123,
            'statement_id': 456,
        }

        second_call_args = mock_request.call_args_list[1]
        assert 'json' in second_call_args[1]
        assert 'data' not in second_call_args[1]
        assert second_call_args[1]['json'] == {
            'account': 123,
            'statement_id': 456,
        }

    def _test_refund_statement_api_delete_token_on_error(self, status_code):
        refund_client = RefundStatementTomanClient()

        Settings.set(CobankTomanAuthenticator.access_token_settings_key, 'abcd')
        Settings.set(CobankTomanAuthenticator.refresh_token_settings_key, 'abcd')
        responses.post('https://dbank.toman.ir/api/v1/revert/', status=status_code)

        with contextlib.suppress(Exception):
            refund_client.refund_statement(self.refund_request)

        assert Settings.get_value(CobankTomanAuthenticator.access_token_settings_key) is None
        assert Settings.get_value(CobankTomanAuthenticator.refresh_token_settings_key) is None

    @responses.activate
    @override_settings(IS_PROD=True)
    def test_refund_statement_api_delete_token_on_403(self):
        self._test_refund_statement_api_delete_token_on_error(403)

    @responses.activate
    @override_settings(IS_PROD=True)
    def test_refund_statement_api_delete_token_on_401(self):
        self._test_refund_statement_api_delete_token_on_error(401)
