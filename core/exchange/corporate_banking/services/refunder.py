from typing import Type, Union

from django.db import transaction

from exchange.base.api import ParseError
from exchange.base.logging import report_exception
from exchange.base.parsers import parse_choices
from exchange.corporate_banking.integrations.toman.dto import RefundData
from exchange.corporate_banking.integrations.toman.refund import RefundStatementTomanClient
from exchange.corporate_banking.models import REFUND_STATUS, STATEMENT_STATUS, CoBankRefund, CoBankStatement
from exchange.corporate_banking.models.constants import COBANK_PROVIDER
from exchange.corporate_banking.services.validators import RefundStatementValidator


class Refunder:
    def __init__(self, provider: COBANK_PROVIDER, batch_size: int = 200):
        """
        provider: Process refund requests for this specific provider.
        batch_size: Maximum number of items to process in a single batch (default: 200).
        """
        self.provider = provider
        self.batch_size = batch_size

    def refund_statement(self, statement: CoBankStatement):
        with transaction.atomic():
            self._validate_statement(statement)
            refund, _ = CoBankRefund.objects.get_or_create(statement=statement)
            if statement.status != STATEMENT_STATUS.refunded:
                statement.status = STATEMENT_STATUS.refunded
                statement.save(update_fields=['status'])

    def get_refunds_latest_status(self):
        for refund_request in self._get_inquiry_candidates():
            self._check_refund_request_status(refund_request)

    def send_new_requests_to_provider(self):
        for refund_request in self._get_new_refund_requests():
            self._send_refund_request(refund_request=refund_request)

    def _send_refund_request(self, refund_request: CoBankRefund):
        with transaction.atomic():
            refund_request = (
                CoBankRefund.objects.filter(pk=refund_request.pk)
                .select_related('statement', 'statement__destination_account')
                .select_for_update(of=('self',), no_key=True)
                .first()
            )
            try:
                refund_client = self._get_refund_client(self.provider)
                refund_response: RefundData = refund_client.refund_statement(refund_request)
                self._update_refund_request(refund_request, refund_response)
            except Exception:
                report_exception()

    def _check_refund_request_status(self, refund_request: CoBankRefund):
        with transaction.atomic():
            refund_request = (
                CoBankRefund.objects.filter(pk=refund_request.pk)
                .select_related('statement', 'statement__destination_account')
                .select_for_update(of=('self',), no_key=True)
                .first()
            )
            try:
                refund_client = self._get_refund_client(self.provider)
                refund_response: RefundData = refund_client.check_refund_status(refund_request)
                self._update_refund_request(refund_request, refund_response)
            except Exception:
                report_exception()

    def _validate_statement(self, statement: CoBankStatement) -> None:
        validator = RefundStatementValidator()
        validator.validate(statement)

    def _get_refund_client(
        self, provider
    ) -> Type[Union[RefundStatementTomanClient,]]:
        """
        provider: The provider identifier from COBANK_PROVIDER
        Raises:
            NotImplementedError: If the provider is not yet implemented
            ValueError: If the provider is unknown
        """
        if provider == COBANK_PROVIDER.toman:
            return RefundStatementTomanClient()
        if provider == COBANK_PROVIDER.jibit:
            # TODO: Implement JibitRefundClient when available
            raise NotImplementedError(f"Refund client for provider '{provider}' is not implemented yet")
        raise ValueError(f'Unknown provider: {provider}')

    def _update_refund_request(self, refund_request: CoBankRefund, refund_response: RefundData):
        refund_request.retry = refund_request.retry + 1
        refund_request.provider_response.append(refund_response.api_response)
        if refund_response.status:
            try:
                refund_request.status = parse_choices(REFUND_STATUS, refund_response.status)
            except ParseError:
                refund_request.status = REFUND_STATUS.unknown
        elif refund_request.status == REFUND_STATUS.new:
            refund_request.status = REFUND_STATUS.sent_to_provider
        if refund_response.transfer_id:
            refund_request.provider_refund_id = refund_response.transfer_id
        refund_request.save(update_fields=('retry', 'provider_response', 'status', 'provider_refund_id'))

    def _get_inquiry_candidates(self):
        return (
            CoBankRefund.objects.filter(
                status__in=CoBankRefund.INQUIRABLE_STATUSES,
                statement__destination_account__provider=self.provider,
            )
            .select_related('statement__destination_account')
            .order_by('created_at')[: self.batch_size]
        )

    def _get_new_refund_requests(self):
        return (
            CoBankRefund.objects.filter(
                status=REFUND_STATUS.new,
                statement__destination_account__provider=self.provider,
            )
            .select_related('statement__destination_account')
            .order_by('created_at')[: self.batch_size]
        )
