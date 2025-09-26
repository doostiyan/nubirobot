import decimal
from datetime import datetime
from decimal import Decimal
from typing import Optional

from exchange.base.constants import MONETARY_DECIMAL_PLACES
from exchange.base.logging import report_exception
from exchange.corporate_banking.exceptions import InvalidTimestampException, StatementDataInvalidAmountException
from exchange.corporate_banking.integrations.converters.base_statement_converter import BaseStatementConverter
from exchange.corporate_banking.models import STATEMENT_TYPE, CoBankStatement
from exchange.wallet.constants import DEPOSIT_MAX_DIGITS


class JibitStatementConverter(BaseStatementConverter):
    def convert(self) -> Optional[CoBankStatement]:
        try:
            amount = self._validate_amount(self.statement_data.debitAmount, self.statement_data.creditAmount)
            if amount is None:
                return None

            return CoBankStatement(
                amount=amount,
                tp=self._get_tp(self.statement_data.creditAmount),
                tracing_number=self.statement_data.bankReferenceNumber,
                transaction_datetime=self._parse_iso_datetime(self.statement_data.timestamp),
                payment_id=self.statement_data.payId,
                source_account=self._get_source_account(
                    self.statement_data.sourceIdentifier, self.statement_data.sourceIban, self.statement_data.recordType
                ),
                source_iban=self.statement_data.sourceIban,
                source_card=self._get_source_card(self.statement_data.sourceIdentifier, self.statement_data.recordType),
                provider_statement_id=self.statement_data.referenceNumber,
                api_response=self.statement_data.apiResponse,
            )
        except (InvalidTimestampException, StatementDataInvalidAmountException):
            report_exception()

    @staticmethod
    def _validate_amount(debit_amount: Optional[int], credit_amount: Optional[int]) -> Optional[int]:
        debit_amount = -abs(Decimal(debit_amount)) if debit_amount is not None else None
        credit_amount = abs(Decimal(credit_amount)) if credit_amount is not None else None
        if debit_amount and credit_amount:
            raise StatementDataInvalidAmountException(
                code='BOTH_AMOUNTS_SET', message='Statement data contains both debit and credit amounts.'
            )
        amount = credit_amount or debit_amount
        if amount is None:
            return None
        if abs(amount) >= Decimal(f'1e{DEPOSIT_MAX_DIGITS - MONETARY_DECIMAL_PLACES}'):
            return None
        return amount

    @staticmethod
    def _parse_iso_datetime(datetime_str: Optional[str]) -> Optional[datetime]:
        if not datetime_str:
            raise InvalidTimestampException(
                code='INVALID_TIMESTAMP',
                message=f'Empty timestamp string received',
            )
        try:
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except ValueError:
            raise InvalidTimestampException(
                code='INVALID_TIMESTAMP', message=f'Invalid timestamp format: "{datetime_str}"'
            )

    @staticmethod
    def _get_source_account(
        source_identifier: Optional[str], source_iban: Optional[str], record_type: Optional[str]
    ) -> Optional[str]:
        if not source_identifier or source_identifier == source_iban or record_type == 'VARIZ_CARD':
            return None
        return source_identifier[:25]

    @staticmethod
    def _get_source_card(source_identifier: Optional[str], record_type: str) -> Optional[str]:
        if record_type == 'VARIZ_CARD':
            return source_identifier.replace("-", "")

    @staticmethod
    def _get_tp(credit_amount: Optional[decimal.Decimal]) -> Optional[str]:
        if credit_amount:
            return STATEMENT_TYPE.deposit
        return STATEMENT_TYPE.withdraw
