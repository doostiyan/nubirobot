from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from exchange.corporate_banking.crons import RefundInquiryRequestsHandlerCron, RefundRequestsHandlerCron
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
from exchange.corporate_banking.services.settler import Settler
from exchange.corporate_banking.tasks import change_statement_status_by_admin_task


class TestRefundCronAndTasks(TestCase):
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
            status=STATEMENT_STATUS.new,
            source_account='SRC.9876',
        )
        self.statement2 = CoBankStatement.objects.create(
            amount=Decimal('20000'),
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

        self.task = change_statement_status_by_admin_task

    def test_integration_between_settler_and_refunder(self):
        """
        Test the integration between Settler's _refund_statement method and Refunder.
        """

        # Create a statement that will be refunded
        statement = CoBankStatement.objects.create(
            amount=Decimal('30000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRC-003',
            transaction_datetime='2025-01-05T03:33:13Z',
            destination_account=self.bank_account,
            status=STATEMENT_STATUS.rejected,
            source_account='SRC.9878',
            provider_statement_id='12345',
        )

        # Simulate admin refunding the statement
        settler = Settler()
        settler.change_statement_status(
            statement_pk=statement.pk,
            changes={'status': STATEMENT_STATUS.refunded},
        )

        # Verify statement status
        statement.refresh_from_db()
        assert statement.status == STATEMENT_STATUS.refunded

    @patch('exchange.corporate_banking.services.settler.Refunder')
    def test_refund_statement_task(self, mock_refunder):
        mock_refunder_instance = mock_refunder.return_value
        mock_refunder_instance.refund_statement.return_value = None

        self.statement.status = STATEMENT_STATUS.rejected
        self.statement.save()

        self.statement2.status = STATEMENT_STATUS.rejected
        self.statement2.save()

        self.task(self.statement.pk, {'status': STATEMENT_STATUS.refunded})
        self.task(self.statement2.pk, {'status': STATEMENT_STATUS.refunded})

        assert mock_refunder.call_count == 2
        assert mock_refunder_instance.refund_statement.call_count == 2
        mock_refunder_instance.refund_statement.assert_any_call(self.statement)
        mock_refunder_instance.refund_statement.assert_any_call(self.statement2)

    @patch('exchange.corporate_banking.services.settler.Refunder')
    def test_refund_statement_task_with_exception(self, mock_refunder):
        mock_refunder_instance = mock_refunder.return_value
        mock_refunder_instance.refund_statement.side_effect = [Exception('Error'), None]
        self.statement.status = STATEMENT_STATUS.rejected
        self.statement.save()

        with self.assertRaises(Exception):
            self.task(self.statement.pk, {'status': STATEMENT_STATUS.refunded})

        assert mock_refunder.call_count == 1
        assert mock_refunder_instance.refund_statement.call_count == 1
        mock_refunder_instance.refund_statement.assert_any_call(self.statement)

    @patch('exchange.corporate_banking.crons.Refunder')
    @patch('exchange.corporate_banking.crons.report_exception')
    def test_refund_requests_handler_cron_new_requests(
        self,
        mock_report_exception,
        mock_refunder,
    ):
        CoBankRefund.objects.create(
            statement=self.statement,
            status=REFUND_STATUS.new,
        )
        CoBankRefund.objects.create(
            statement=self.statement2,
            status=REFUND_STATUS.new,
        )
        mock_refunder_instance = mock_refunder.return_value
        mock_refunder_instance.send_new_requests_to_provider.return_value = None

        cron = RefundRequestsHandlerCron()
        cron.run()

        # Verify that Refunder was called with the correct provider filter
        mock_refunder.assert_called_once_with(provider=COBANK_PROVIDER.toman)
        mock_refunder_instance.send_new_requests_to_provider.assert_called_once()
        report_exception_instance = mock_report_exception.return_value
        assert report_exception_instance.call_count == 0

    @patch('exchange.corporate_banking.crons.Refunder')
    def test_refund_inquiry_requests_handler_cron(self, mock_refunder):
        mock_refunder_instance = mock_refunder.return_value
        mock_refunder_instance.get_refunds_latest_status.return_value = None

        cron = RefundInquiryRequestsHandlerCron()
        cron.run()

        # Verify that Refunder was called with the correct provider filter
        mock_refunder.assert_called_once_with(provider=COBANK_PROVIDER.toman)
        mock_refunder_instance.get_refunds_latest_status.assert_called_once()

        assert mock_refunder_instance._check_refund_request_status.call_count == 0

    @patch('exchange.corporate_banking.crons.Refunder')
    def test_refund_requests_handler_cron_no_requests(self, mock_refunder):
        mock_refunder_instance = mock_refunder.return_value
        mock_refunder_instance.send_new_requests_to_provider.return_value = []
        mock_refunder_instance.get_refunds_latest_status.return_value = []

        cron = RefundRequestsHandlerCron()
        cron.run()

        mock_refunder.assert_called_once_with(provider=COBANK_PROVIDER.toman)
        mock_refunder_instance.send_new_requests_to_provider.assert_called_once()
        assert mock_refunder_instance.get_refunds_latest_status.call_count == 0

        cron = RefundInquiryRequestsHandlerCron()
        cron.run()

        mock_refunder_instance.get_refunds_latest_status.assert_called_once()
        assert mock_refunder_instance.send_new_requests_to_provider.call_count == 1

    @patch('exchange.corporate_banking.services.refunder.RefundStatementTomanClient')
    def test_refund_process_end_to_end(self, mock_toman_client):
        """
        Test the full refund process from statement rejection to cron processing.
        """
        # Create a statement in rejected status
        statement = CoBankStatement.objects.create(
            amount=Decimal('30000'),
            tp=STATEMENT_TYPE.deposit,
            tracing_number='TRC-003',
            transaction_datetime='2025-01-05T03:33:13Z',
            destination_account=self.bank_account,
            status=STATEMENT_STATUS.rejected,
            source_account='SRC.9879',
            provider_statement_id='12345',
        )

        # Mock the Toman client responses
        refund_response_data = RefundData.from_data(self.sample_toman_response)

        mock_toman_client.return_value.refund_statement.return_value = refund_response_data
        mock_toman_client.return_value.check_refund_status.return_value = refund_response_data

        # STEP 1: Admin refunds the statement
        settler = Settler()
        settler.change_statement_status(
            statement_pk=statement.pk,
            changes={'status': STATEMENT_STATUS.refunded},
        )

        # Verify statement status and refund creation
        statement.refresh_from_db()
        assert statement.status == STATEMENT_STATUS.refunded  # Statement status should be refunded

        # Check that a refund request was created
        refund = CoBankRefund.objects.get(statement=statement)
        assert refund.status == REFUND_STATUS.new

        # STEP 2: Cron runs to send new refund requests to provider
        cron_refund_requests = RefundRequestsHandlerCron()
        cron_refund_requests.run()

        # Check that the refund status was updated
        refund.refresh_from_db()
        assert refund.status == REFUND_STATUS.pending
        assert refund.provider_refund_id == self.transfer_uid
        assert refund.retry == 1

        # STEP 3: Cron runs to inquire about refund status
        cron_inquiry = RefundInquiryRequestsHandlerCron()
        cron_inquiry.run()

        # Check that the refund was processed
        refund.refresh_from_db()
        assert refund.retry == 2  # Should be incremented again
        assert len(refund.provider_response) == 2  # Should have two responses now
