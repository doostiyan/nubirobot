import datetime
from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase

from exchange.base.calendar import ir_now
from exchange.base.parsers import parse_iso_date
from exchange.corporate_banking.exceptions import ThirdPartyClientUnavailable
from exchange.corporate_banking.integrations.jibit.base import BaseJibitAPIClient
from exchange.corporate_banking.integrations.jibit.dto import StatementItemDTO, TransferDTO, TransferItemDTO
from exchange.corporate_banking.integrations.jibit.refund import RefundStatementJibitClient
from exchange.corporate_banking.models import (
    ACCOUNT_TP,
    COBANK_PROVIDER,
    NOBITEX_BANK_CHOICES,
    STATEMENT_STATUS,
    STATEMENT_TYPE,
    CoBankAccount,
    CoBankStatement,
)


class TestRefundStatementJibitClient(TestCase):
    """Tests for RefundStatementJibitClient."""

    def setUp(self):
        self.bank_account = CoBankAccount.objects.create(
            provider=COBANK_PROVIDER.jibit,
            provider_bank_id=4,
            bank=NOBITEX_BANK_CHOICES.saderat,
            iban='IR999999999999999999999991',
            account_number='111222333',
            account_tp=ACCOUNT_TP.operational,
        )
        self.statement = CoBankStatement.objects.create(
            amount=10_000_000_0,
            tp=STATEMENT_TYPE.deposit,
            tracing_number='abcd1234',
            transaction_datetime=ir_now(),
            status=STATEMENT_STATUS.executed,
            destination_account=self.bank_account,
            payment_id='12345',
            provider_statement_id='1234567890',
        )
        self.jibit_client = RefundStatementJibitClient(self.statement)

        # Sample response data
        self.refund_statement_sample = {
            'referenceNumber': 'JBTR12341234',
            'accountIban': 'IR999999999999999999999991',
            'bankReferenceNumber': 'SAD12345',
            'bankTransactionId': 'TRX987654',
            'balance': 100000000,
            'timestamp': '2025-05-21T09:22:18.351Z',
            'creditAmount': 10000000,
            'debitAmount': 0,
            'rawData': 'SAMPLE_RAW_DATA',
            'sourceIdentifier': 'SRCA123',
            'destinationIdentifier': 'DESTB456',
            'sourceIban': 'IR120120000001234567890123',
            'destinationIban': 'IR999999999999999999999991',
            'sourceName': 'Source Account',
            'destinationName': 'Destination Account',
            'payId': 'PAYID123',
            'recordType': 'BARDASHT_RESERVE',
            'merchantVerificationStatus': 'VERIFIED',
            'kytStatus': 'CLEAR',
            'refundType': 'FULL_REFUND',
            'refundTrackId': 'REFTRACK123',
            'relatedStatementRecord': 'STMT123456',
            'createdAt': '2025-05-21T09:22:18.351Z',
        }

        self.get_refund_status_sample = {
            'referenceNumber': 'JBTR12341234',
            'trackId': 'TRACK9876',
            'ownerCode': 'OWNER123',
            'requestChannel': 'API',
            'type': 'REFUND',
            'sourceIban': 'IR120120000001234567890123',
            'destinationIban': 'IR999999999999999999999991',
            'totalAmount': 10000000,
            'primeCount': 1,
            'createdAt': '2025-05-21T09:23:03.338Z',
            'updatedAt': '2025-05-21T09:25:03.338Z',
            'records': [
                {
                    'referenceNumber': 'JBTR12341234',
                    'bankReferenceNumber': 'SAD12345',
                    'failReason': '',
                    'trackId': 'TRACK9876',
                    'recordType': 'PRIME',
                    'sourceAccountIban': 'IR120120000001234567890123',
                    'destinationIban': 'IR999999999999999999999991',
                    'destinationAccountNumber': '111222333',
                    'destinationFirstName': 'Mostafa',
                    'destinationLastName': 'Heidarian',
                    'amount': 10000000,
                    'payId': 'PAYID123',
                    'transferType': 'NORMAL',
                    'state': 'TRANSFERRED',
                    'lastSubmitSuccessAt': '2025-05-21T09:24:03.338Z',
                    'createdAt': '2025-05-21T09:23:03.338Z',
                    'updatedAt': '2025-05-21T09:24:03.338Z',
                },
            ],
        }

    def check_statement_result(self, result, data):
        assert isinstance(result, StatementItemDTO)
        assert result.apiResponse == data

        assert result.referenceNumber == 'JBTR12341234'
        assert result.destinationAccount == self.bank_account.pk
        assert result.refundType == data['refundType']
        assert result.bankReferenceNumber == data['bankReferenceNumber']
        assert result.bankTransactionId == data['bankTransactionId']
        assert result.timestamp == data['timestamp']
        assert result.sourceIban == data['sourceIban']
        assert result.destinationIban == data['destinationIban']
        assert result.accountIban == data['accountIban']
        assert result.sourceIdentifier == data['sourceIdentifier']
        assert result.destinationIdentifier == data['destinationIdentifier']
        assert result.balance == data['balance']
        assert result.debitAmount == data['debitAmount']
        assert result.creditAmount == data['creditAmount']
        assert result.rawData == data['rawData']
        assert result.payId == data['payId']
        assert result.recordType == data['recordType']
        assert result.merchantVerificationStatus == data['merchantVerificationStatus']
        assert result.kytStatus == data['kytStatus']
        assert result.refundType == data['refundType']
        assert result.refundTrackId == data['refundTrackId']
        assert result.createdAt == data['createdAt']

    def check_transfer_result(self, result, data):
        assert isinstance(result, TransferDTO)
        assert len(result.records) == 1

        assert result.referenceNumber == 'JBTR12341234'
        assert result.trackId == 'TRACK9876'
        assert result.ownerCode == data['ownerCode']
        assert result.requestChannel == data['requestChannel']
        assert result.type == data['type']
        assert result.sourceIban == data['sourceIban']
        assert result.destinationIban == data['destinationIban']
        assert result.totalAmount == data['totalAmount']
        assert result.primeCount == data['primeCount']
        assert result.createdAt == parse_iso_date(data['createdAt'])
        assert result.updatedAt == parse_iso_date(data['updatedAt'])

        assert len(result.records) == 1
        transfer_item = result.records[0]
        transfer_item_sample = data['records'][0]

        assert isinstance(transfer_item, TransferItemDTO)

        assert transfer_item.referenceNumber == transfer_item_sample['referenceNumber']
        assert transfer_item.bankReferenceNumber == transfer_item_sample['bankReferenceNumber']
        assert transfer_item.failReason == transfer_item_sample['failReason']
        assert transfer_item.trackId == transfer_item_sample['trackId']
        assert transfer_item.recordType == transfer_item_sample['recordType']
        assert transfer_item.sourceAccountIban == transfer_item_sample['sourceAccountIban']
        assert transfer_item.destinationIban == transfer_item_sample['destinationIban']
        assert transfer_item.destinationAccountNumber == transfer_item_sample['destinationAccountNumber']
        assert transfer_item.destinationFirstName == transfer_item_sample['destinationFirstName']
        assert transfer_item.destinationLastName == transfer_item_sample['destinationLastName']
        assert transfer_item.amount == transfer_item_sample['amount']
        assert transfer_item.payId == transfer_item_sample['payId']
        assert transfer_item.transferType == transfer_item_sample['transferType']
        assert transfer_item.state == transfer_item_sample['state']
        assert transfer_item.lastSubmitSuccessAt == parse_iso_date(transfer_item_sample['lastSubmitSuccessAt'])
        assert transfer_item.createdAt == parse_iso_date(transfer_item_sample['createdAt'])
        assert transfer_item.updatedAt == parse_iso_date(transfer_item_sample['updatedAt'])

    def test_init_sets_api_url_correctly(self):
        """Test that initialization sets the correct API URL template."""
        expected_url = '/v1/orders/aug-statement/{iban}/variz/{reference_number}/{action}'
        assert self.jibit_client._base_api_url == expected_url

    @patch.object(BaseJibitAPIClient, '_prepare_headers')
    @patch.object(BaseJibitAPIClient, '_send_request')
    def test_refund_statement_success(self, mock_send, mock_header):
        """Test successful refund statement request."""
        mock_header.return_value = {}
        mock_send.return_value = self.refund_statement_sample

        result = self.jibit_client.refund_statement()
        self.check_statement_result(result, self.refund_statement_sample)

        expected_url = f'/v1/orders/aug-statement/{self.bank_account.iban}/variz/{self.statement.provider_statement_id}/full-refund'
        assert self.jibit_client.api_url == expected_url
        assert self.jibit_client.request_method == 'POST'
        assert self.jibit_client.metric_name == 'cobanking_thirdparty_services__Jibit_requestRefund_'

        mock_send.assert_called_once_with(api_url=expected_url, headers={}, payload={}, retry=1)
        mock_header.assert_called_once()

    @patch.object(BaseJibitAPIClient, '_prepare_headers')
    @patch.object(BaseJibitAPIClient, '_send_request')
    def test_check_refund_status_success(self, mock_send, mock_header):
        """Test successful refund status check."""
        mock_header.return_value = {}
        mock_send.return_value = self.get_refund_status_sample

        result = self.jibit_client.check_refund_status()

        self.check_transfer_result(result, self.get_refund_status_sample)

        expected_url = (
            f'/v1/orders/aug-statement/{self.bank_account.iban}/variz/{self.statement.provider_statement_id}/refund'
        )
        assert self.jibit_client.api_url == expected_url
        assert self.jibit_client.request_method == 'GET'
        assert self.jibit_client.metric_name == 'cobanking_thirdparty_services__Jibit_checkRefundStatus_'

        mock_send.assert_called_once_with(api_url=expected_url, headers={}, payload={}, retry=1)
        mock_header.assert_called_once()

    @patch.object(BaseJibitAPIClient, '_prepare_headers')
    @patch.object(BaseJibitAPIClient, '_send_request')
    def test_make_statement_failed_success(self, mock_send, mock_header):
        """Test successful statement failure marking."""
        mock_header.return_value = {}
        mock_send.return_value = self.refund_statement_sample

        result = self.jibit_client.make_statement_failed()
        self.check_statement_result(result, self.refund_statement_sample)

        expected_url = (
            f'/v1/orders/aug-statement/{self.bank_account.iban}/variz/{self.statement.provider_statement_id}/fail'
        )
        assert self.jibit_client.api_url == expected_url
        assert self.jibit_client.request_method == 'GET'
        assert self.jibit_client.metric_name == 'cobanking_thirdparty_services__Jibit_requestFail_'

        mock_send.assert_called_once_with(api_url=expected_url, headers={}, payload={}, retry=1)
        mock_header.assert_called_once()

    @patch.object(BaseJibitAPIClient, '_prepare_headers')
    @patch.object(BaseJibitAPIClient, '_send_request')
    def test_http_error_raises_third_party_unavailable(self, mock_send, mock_header):
        """Test that HTTP errors are properly converted to ThirdPartyClientUnavailable."""
        mock_header.return_value = {}
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {'message': 'Internal Server Error'}
        http_error = requests.exceptions.HTTPError('Server Error')
        http_error.response = mock_response
        mock_send.side_effect = http_error

        with self.assertRaises(ThirdPartyClientUnavailable) as context:
            self.jibit_client.refund_statement()

        exception = context.exception
        assert exception.code == 'HTTPError'
        assert exception.status_code == 500
        assert 'Jibit API currently unavailable' in exception.message
        assert 'Internal Server Error' in exception.message

    @patch.object(BaseJibitAPIClient, '_prepare_headers')
    @patch.object(BaseJibitAPIClient, '_send_request')
    def test_http_error_with_jibit_error_format(self, mock_send, mock_header):
        """Test that HTTP errors with Jibit error format are properly handled."""
        mock_header.return_value = {}
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'fingerprint': '12345',
            'errors': [
                {
                    'code': 'Authentication.failed',
                    'message': 'Invalid authentication credentials',
                },
            ],
        }
        http_error = requests.exceptions.HTTPError('Bad Request')
        http_error.response = mock_response
        mock_send.side_effect = http_error

        with self.assertRaises(ThirdPartyClientUnavailable) as context:
            self.jibit_client.refund_statement()

        exception = context.exception
        assert exception.code == 'Authentication.failed'
        assert exception.status_code == 400
        assert 'Jibit API currently unavailable' in exception.message
        assert 'Invalid authentication credentials' in exception.message

    @patch.object(BaseJibitAPIClient, '_prepare_headers')
    @patch.object(BaseJibitAPIClient, '_send_request')
    def test_http_error_with_multiple_jibit_errors(self, mock_send, mock_header):
        """Test that HTTP errors with multiple Jibit errors use the first error."""
        mock_header.return_value = {}
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'fingerprint': '12345',
            'errors': [
                {
                    'code': 'Bad.request',
                    'message': 'Invalid request format',
                },
                {
                    'code': 'Internal.error',
                    'message': 'Server error occurred',
                },
            ],
        }
        http_error = requests.exceptions.HTTPError('Bad Request')
        http_error.response = mock_response
        mock_send.side_effect = http_error

        with self.assertRaises(ThirdPartyClientUnavailable) as context:
            self.jibit_client.refund_statement()

        exception = context.exception
        assert exception.code == 'Bad.request'
        assert exception.status_code == 400
        assert 'Invalid request format' in exception.message

    @patch.object(BaseJibitAPIClient, '_prepare_headers')
    @patch.object(BaseJibitAPIClient, '_send_request')
    def test_http_error_with_empty_errors_array(self, mock_send, mock_header):
        """Test that HTTP errors with empty errors array fall back to original error."""
        mock_header.return_value = {}
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            'fingerprint': '12345',
            'errors': [],
        }
        http_error = requests.exceptions.HTTPError('Server Error')
        http_error.response = mock_response
        mock_send.side_effect = http_error

        with self.assertRaises(ThirdPartyClientUnavailable) as context:
            self.jibit_client.refund_statement()

        exception = context.exception
        assert exception.code == 'HTTPError'
        assert exception.status_code == 500
        assert 'Server Error' in exception.message

    @patch.object(BaseJibitAPIClient, '_prepare_headers')
    @patch.object(BaseJibitAPIClient, '_send_request')
    def test_connection_error_raises_third_party_unavailable(self, mock_send, mock_header):
        """Test that connection errors are properly handled."""
        mock_header.return_value = {}
        mock_send.side_effect = requests.exceptions.ConnectionError('Connection failed')

        with self.assertRaises(ThirdPartyClientUnavailable) as context:
            self.jibit_client.check_refund_status()

        exception = context.exception
        assert exception.code == 'ConnectionError'
        assert exception.status_code == -1

    @patch.object(BaseJibitAPIClient, '_prepare_headers')
    @patch.object(BaseJibitAPIClient, '_send_request')
    def test_timeout_error_raises_third_party_unavailable(self, mock_send, mock_header):
        """Test that timeout errors are properly handled."""
        mock_header.return_value = {}
        mock_send.side_effect = requests.exceptions.Timeout('Request timed out')

        with self.assertRaises(ThirdPartyClientUnavailable):
            self.jibit_client.refund_statement()

    @patch.object(BaseJibitAPIClient, '_prepare_headers')
    @patch.object(BaseJibitAPIClient, '_send_request')
    def test_unexpected_error_raises_third_party_unavailable(self, mock_send, mock_header):
        """Test that unexpected errors are properly handled."""
        mock_header.return_value = {}
        mock_send.side_effect = ValueError('Unexpected error')

        with self.assertRaises(ThirdPartyClientUnavailable) as context:
            self.jibit_client.refund_statement()

        exception = context.exception
        assert exception.code == 'ValueError'
        assert exception.status_code == -1

    @patch.object(BaseJibitAPIClient, '_prepare_headers')
    @patch.object(BaseJibitAPIClient, '_send_request')
    def test_request_exception_raises_third_party_unavailable(self, mock_send, mock_header):
        """Test that RequestException errors are properly handled."""
        mock_header.return_value = {}
        mock_send.side_effect = requests.exceptions.RequestException('Request failed')

        with self.assertRaises(ThirdPartyClientUnavailable) as context:
            self.jibit_client.refund_statement()

        exception = context.exception
        assert exception.code == 'RequestException'
        assert exception.status_code == -1

    def test_parse_statement_response(self):
        """Test response parsing for statement operations (StatementItemDTO)."""
        result = self.jibit_client._parse_statement_response(self.refund_statement_sample)
        self.check_statement_result(result, self.refund_statement_sample)

    def test_parse_status_check_response(self):
        """Test response parsing for status check operations (TransferDTO)."""
        result = self.jibit_client._parse_status_check_response(self.get_refund_status_sample)
        self.check_transfer_result(result, self.get_refund_status_sample)

    def test_parse_response_filters_invalid_fields(self):
        """Test that response parsing filters out invalid fields for StatementItemDTO."""
        response_with_extra_fields = {
            **self.refund_statement_sample,
            'invalidField': 'should_be_filtered',
            'anotherInvalidField': 123,
        }

        result = self.jibit_client._parse_statement_response(response_with_extra_fields)

        assert isinstance(result, StatementItemDTO)
        # Verify that invalid fields are not present in the DTO
        assert not hasattr(result, 'invalidField')
        assert not hasattr(result, 'anotherInvalidField')

    def test_build_client_unavailable_exception_with_response(self):
        """Test exception building when HTTP response is available."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {'message': 'Not Found'}
        error = requests.exceptions.HTTPError('Not Found')
        error.response = mock_response

        exception = self.jibit_client._build_client_unavailable_exception(error)

        assert isinstance(exception, ThirdPartyClientUnavailable)
        assert exception.code == 'HTTPError'
        assert exception.status_code == 404
        assert 'Jibit API currently unavailable' in exception.message
        assert 'Not Found' in exception.message

    def test_build_client_unavailable_exception_without_response(self):
        """Test exception building when no HTTP response is available."""
        error = requests.exceptions.ConnectionError('Connection failed')

        exception = self.jibit_client._build_client_unavailable_exception(error)

        assert isinstance(exception, ThirdPartyClientUnavailable)
        assert exception.code == 'ConnectionError'
        assert exception.status_code == -1

    def test_build_client_unavailable_exception_with_invalid_json(self):
        """Test exception building when response JSON is invalid."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.side_effect = ValueError('Invalid JSON')
        error = requests.exceptions.HTTPError('Server Error')
        error.response = mock_response

        exception = self.jibit_client._build_client_unavailable_exception(error)

        assert isinstance(exception, ThirdPartyClientUnavailable)
        assert exception.code == 'HTTPError'
        assert exception.status_code == 500
        # Should fall back to original error message
        assert 'Server Error' in exception.message
