from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import TestCase

from exchange.corporate_banking.exceptions import RefundValidationException, ThirdPartyClientUnavailable
from exchange.corporate_banking.integrations.toman.dto import RefundData
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
from exchange.corporate_banking.models.constants import COBANK_PROVIDER
from exchange.corporate_banking.services.refunder import Refunder


class TestRefunder(TestCase):
    def setUp(self):
        self.bank_account = CoBankAccount.objects.create(
            provider_bank_id=11,
            bank=NOBITEX_BANK_CHOICES.saman,
            iban='IR999999999999999999999991',
            account_number='10.8593617.1',
            account_owner='راهکار فناوری نویان',
            is_active=True,
            account_tp=ACCOUNT_TP.operational,
            is_deleted=False,
            provider=COBANK_PROVIDER.toman,
        )
        self.statement = CoBankStatement.objects.create(
            amount=Decimal('10000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRC-001',
            transaction_datetime='2025-01-05T03:33:13Z',
            destination_account=self.bank_account,
            status=STATEMENT_STATUS.rejected,
            source_account='SRC.9876',
            provider_statement_id='1234567890',
        )
        self.statement2 = CoBankStatement.objects.create(
            amount=Decimal('10000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRC-002',
            transaction_datetime='2025-01-05T03:33:13Z',
            destination_account=self.bank_account,
            status=STATEMENT_STATUS.new,
            source_account='SRC.9877',
        )
        self.transfer_uid = 'a524ffb9-34c3-4903-be9b-e82ec922b45f'
        self.sample_toman_response = {
            'id': 1,
            'transfer': {
                'uuid': self.transfer_uid,
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
        self.refunder = Refunder(provider=COBANK_PROVIDER.toman)

    def test_refunder_init_with_required_provider(self):
        refunder = Refunder(provider=COBANK_PROVIDER.toman)
        assert refunder.provider == COBANK_PROVIDER.toman
        assert refunder.batch_size == 200  # default value

    def test_refunder_init_with_custom_batch_size(self):
        refunder = Refunder(provider=COBANK_PROVIDER.toman, batch_size=50)
        assert refunder.provider == COBANK_PROVIDER.toman
        assert refunder.batch_size == 50

    def test_refund_statement_new_refund(self):
        self.refunder.refund_statement(self.statement)
        refund_request = CoBankRefund.objects.get(statement=self.statement)

        assert refund_request.status == REFUND_STATUS.new

        self.statement.refresh_from_db()
        assert self.statement.status == STATEMENT_STATUS.refunded

    @patch('exchange.corporate_banking.services.refunder.RefundStatementValidator.validate')
    def test_refund_statement_does_not_call_save_if_already_refunded(self, mock_validator):
        mock_validator.return_value.validate.return_value = None
        refunder = Refunder(provider=COBANK_PROVIDER.toman)
        self.statement.status = STATEMENT_STATUS.refunded
        self.statement.save()
        with patch.object(CoBankStatement, 'save') as mock_save:
            refunder.refund_statement(self.statement)

        mock_save.assert_not_called()

    @patch('exchange.corporate_banking.services.refunder.RefundStatementValidator.validate')
    def test_refund_statement_new_refund_validation_error(self, mock_validator):
        mock_validator.side_effect = RefundValidationException('ObjectIsNotValid')
        with pytest.raises(RefundValidationException):
            self.refunder.refund_statement(self.statement)

        assert mock_validator.call_count == 1
        assert not CoBankRefund.objects.filter(statement=self.statement).exists()
        assert self.statement.status == STATEMENT_STATUS.rejected

    def test_refund_statement_new_refund_validation_error_on_iban(self):
        self.statement.destination_account.iban = ''
        self.statement.destination_account.save()

        with self.assertRaises(RefundValidationException) as context:
            self.refunder.refund_statement(self.statement)

        assert str(context.exception) == 'StatementDestinationAccountWithoutIBAN'

    def test_refund_statement_new_refund_validation_error_on_missing_provider_id(self):
        self.statement.provider_statement_id = ''
        self.statement.save()

        with self.assertRaises(RefundValidationException) as context:
            self.refunder.refund_statement(self.statement)

        assert str(context.exception) == 'StatementWithoutProviderStatementID'

    @patch('exchange.corporate_banking.services.refunder.RefundStatementValidator')
    def test_refund_statement_existing_refund(self, mock_validator):
        CoBankRefund.objects.create(
            statement=self.statement,
            status=REFUND_STATUS.new,
        )
        mock_validator.return_value.validate.return_value = None
        assert self.statement.status == STATEMENT_STATUS.rejected

        Refunder(provider=COBANK_PROVIDER.toman).refund_statement(self.statement)

        assert mock_validator.return_value.validate.call_count == 1
        assert CoBankRefund.objects.filter(statement=self.statement).count() == 1

        self.statement.refresh_from_db()
        assert self.statement.status == STATEMENT_STATUS.refunded

    @patch('exchange.corporate_banking.services.refunder.RefundStatementTomanClient')
    def test_send_refund_request_success(self, mock_client):
        refund = CoBankRefund.objects.create(
            statement=self.statement,
            status=REFUND_STATUS.new,
        )
        refund_data = RefundData.from_data(self.sample_toman_response)
        mock_client.return_value.refund_statement.return_value = refund_data

        self.refunder._send_refund_request(refund)

        mock_client.return_value.refund_statement.assert_called_once_with(refund)
        refund.refresh_from_db()
        assert refund.status == REFUND_STATUS.pending
        assert refund.provider_refund_id == self.transfer_uid
        assert refund.retry == 1

        assert refund.provider_response == [
            self.sample_toman_response,
        ]

    @patch('exchange.corporate_banking.services.refunder.RefundStatementTomanClient')
    def test_send_refund_request_success_without_status_in_response(self, mock_client):
        refund = CoBankRefund.objects.create(
            statement=self.statement,
            status=REFUND_STATUS.new,
        )

        self.sample_toman_response.pop('status', None)
        refund_data = RefundData.from_data(self.sample_toman_response)
        mock_client.return_value.refund_statement.return_value = refund_data

        self.refunder._send_refund_request(refund)

        mock_client.return_value.refund_statement.assert_called_once_with(refund)
        refund.refresh_from_db()
        assert refund.status == REFUND_STATUS.unknown
        assert refund.provider_refund_id == self.transfer_uid
        assert refund.retry == 1
        assert refund.provider_response == [
            self.sample_toman_response,
        ]

    @patch('exchange.corporate_banking.services.refunder.RefundStatementTomanClient')
    @patch('exchange.corporate_banking.services.refunder.report_exception')
    def test_send_refund_request_failure_no_retry(self, mock_report_exception, mock_client):
        refund = CoBankRefund.objects.create(
            statement=self.statement,
            status=REFUND_STATUS.new,
        )
        mock_client.return_value.refund_statement.side_effect = ThirdPartyClientUnavailable(
            code='Timeout',
            message='Client Unavailable',
            status_code=408,
        )

        self.refunder._send_refund_request(refund)

        mock_report_exception.assert_called_once()
        refund.refresh_from_db()
        assert refund.status == REFUND_STATUS.new
        assert refund.retry == 0

    @patch('exchange.corporate_banking.services.refunder.RefundStatementTomanClient')
    def test_check_refund_request_status_pending(self, mock_client):
        refund = CoBankRefund.objects.create(
            statement=self.statement,
            status=REFUND_STATUS.pending,
        )
        refund_data = RefundData.from_data(self.sample_toman_response)
        mock_client.return_value.check_refund_status.return_value = refund_data

        self.refunder._check_refund_request_status(refund)

        mock_client.return_value.check_refund_status.assert_called_once_with(refund)
        refund.refresh_from_db()
        assert refund.status == REFUND_STATUS.pending
        assert refund.provider_refund_id == self.transfer_uid
        assert refund.retry == 1

    @patch('exchange.corporate_banking.services.refunder.RefundStatementTomanClient')
    def test_check_refund_request_status_bad_response(self, mock_client):
        refund = CoBankRefund.objects.create(
            statement=self.statement,
            status=REFUND_STATUS.pending,
        )
        self.sample_toman_response['status'] = -1
        refund_data = RefundData.from_data(self.sample_toman_response)
        mock_client.return_value.check_refund_status.return_value = refund_data

        self.refunder._check_refund_request_status(refund)

        mock_client.return_value.check_refund_status.assert_called_once_with(refund)
        refund.refresh_from_db()
        assert refund.status == REFUND_STATUS.unknown
        assert refund.provider_refund_id == self.transfer_uid
        assert refund.retry == 1

    @patch('exchange.corporate_banking.services.refunder.RefundStatementTomanClient')
    def test_check_refund_request_status_completed(self, mock_client):
        refund = CoBankRefund.objects.create(
            statement=self.statement,
            status=REFUND_STATUS.pending,
        )

        self.sample_toman_response['status'] = 6
        refund_data = RefundData.from_data(self.sample_toman_response)
        mock_client.return_value.check_refund_status.return_value = refund_data

        self.refunder._check_refund_request_status(refund)

        mock_client.return_value.check_refund_status.assert_called_once_with(refund)
        refund.refresh_from_db()
        assert refund.status == REFUND_STATUS.completed
        assert refund.retry == 1

    @patch('exchange.corporate_banking.services.refunder.RefundStatementTomanClient')
    @patch('exchange.corporate_banking.services.refunder.report_exception')
    def test_check_refund_request_status_failure(self, mock_report_exception, mock_client):
        refund = CoBankRefund.objects.create(
            statement=self.statement,
            status=REFUND_STATUS.pending,
        )
        mock_client.return_value.check_refund_status.side_effect = ThirdPartyClientUnavailable(
            code='Timeout',
            message='Client Unavailable',
            status_code=408,
        )

        self.refunder._check_refund_request_status(refund)

        mock_report_exception.assert_called_once()
        refund.refresh_from_db()
        assert refund.status == REFUND_STATUS.pending
        assert refund.retry == 0

    def test_get_inquiry_candidates(self):
        refund1 = CoBankRefund.objects.create(
            statement=self.statement,
            status=REFUND_STATUS.pending,
        )
        CoBankRefund.objects.create(
            statement=self.statement2,
            status=REFUND_STATUS.completed,
        )

        candidates = self.refunder._get_inquiry_candidates()

        assert len(candidates) == 1
        assert candidates[0].pk == refund1.pk
        assert candidates[0].status == REFUND_STATUS.pending

    def test_get_inquiry_candidates_filters_by_provider(self):
        # Create another bank account with different provider
        other_bank_account = CoBankAccount.objects.create(
            provider_bank_id=12,
            bank=NOBITEX_BANK_CHOICES.saman,
            iban='IR999999999999999999999992',
            account_number='10.8593617.2',
            account_owner='راهکار فناوری نویان',
            is_active=True,
            account_tp=ACCOUNT_TP.operational,
            is_deleted=False,
            provider=COBANK_PROVIDER.jibit,
        )

        other_statement = CoBankStatement.objects.create(
            amount=Decimal('15000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRC-003',
            transaction_datetime='2025-01-05T03:33:13Z',
            destination_account=other_bank_account,
            status=STATEMENT_STATUS.rejected,
            source_account='SRC.9878',
        )

        # Create refunds for both providers
        refund_toman = CoBankRefund.objects.create(
            statement=self.statement,
            status=REFUND_STATUS.pending,
        )
        refund_jibit = CoBankRefund.objects.create(
            statement=other_statement,
            status=REFUND_STATUS.pending,
        )

        # Refunder with toman filter should only return toman refunds
        toman_refunder = Refunder(provider=COBANK_PROVIDER.toman)
        candidates = toman_refunder._get_inquiry_candidates()

        assert len(candidates) == 1
        assert candidates[0].pk == refund_toman.pk

        # Refunder with jibit filter should only return jibit refunds
        jibit_refunder = Refunder(provider=COBANK_PROVIDER.jibit)
        candidates = jibit_refunder._get_inquiry_candidates()

        assert len(candidates) == 1
        assert candidates[0].pk == refund_jibit.pk

    def test_get_new_refund_requests(self):
        refund1 = CoBankRefund.objects.create(
            statement=self.statement,
            status=REFUND_STATUS.new,
        )
        CoBankRefund.objects.create(
            statement=self.statement2,
            status=REFUND_STATUS.pending,
        )

        requests = self.refunder._get_new_refund_requests()

        assert len(requests) == 1
        assert requests[0].pk == refund1.pk
        assert requests[0].status == REFUND_STATUS.new

    def test_get_new_refund_requests_filters_by_provider(self):
        # Create another bank account with different provider
        other_bank_account = CoBankAccount.objects.create(
            provider_bank_id=12,
            bank=NOBITEX_BANK_CHOICES.saman,
            iban='IR999999999999999999999992',
            account_number='10.8593617.2',
            account_owner='راهکار فناوری نویان',
            is_active=True,
            account_tp=ACCOUNT_TP.operational,
            is_deleted=False,
            provider=COBANK_PROVIDER.jibit,
        )

        other_statement = CoBankStatement.objects.create(
            amount=Decimal('15000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRC-003',
            transaction_datetime='2025-01-05T03:33:13Z',
            destination_account=other_bank_account,
            status=STATEMENT_STATUS.rejected,
            source_account='SRC.9878',
        )

        # Create refunds for both providers
        refund_toman = CoBankRefund.objects.create(
            statement=self.statement,
            status=REFUND_STATUS.new,
        )
        refund_jibit = CoBankRefund.objects.create(
            statement=other_statement,
            status=REFUND_STATUS.new,
        )

        # Refunder with toman filter should only return toman refunds
        toman_refunder = Refunder(provider=COBANK_PROVIDER.toman)
        requests = toman_refunder._get_new_refund_requests()

        assert len(requests) == 1
        assert requests[0].pk == refund_toman.pk

        # Refunder with jibit filter should only return jibit refunds
        jibit_refunder = Refunder(provider=COBANK_PROVIDER.jibit)
        requests = jibit_refunder._get_new_refund_requests()

        assert len(requests) == 1
        assert requests[0].pk == refund_jibit.pk

    def test_batch_size_limits_results(self):
        for i in range(5):
            statement = CoBankStatement.objects.create(
                amount=Decimal('10000'),
                tp=STATEMENT_TYPE.deposit,
                tracing_number=f'TRC-{i+10}',
                transaction_datetime='2025-01-05T03:33:13Z',
                destination_account=self.bank_account,
                status=STATEMENT_STATUS.rejected,
                source_account=f'SRC.{i+1000}',
            )
            CoBankRefund.objects.create(
                statement=statement,
                status=REFUND_STATUS.new,
            )

        # Test with small batch size
        small_batch_refunder = Refunder(provider=COBANK_PROVIDER.toman, batch_size=3)
        requests = small_batch_refunder._get_new_refund_requests()
        assert len(requests) == 3

        # Test with large batch size
        large_batch_refunder = Refunder(provider=COBANK_PROVIDER.toman, batch_size=10)
        requests = large_batch_refunder._get_new_refund_requests()
        assert len(requests) == 5  # Only 5 exist

    def test_refund_dto(self):
        refund_data = RefundData.from_data(self.sample_toman_response)
        assert refund_data.transfer_id == self.transfer_uid
        assert refund_data.transfer.uuid == self.transfer_uid
