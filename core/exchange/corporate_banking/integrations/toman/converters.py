from decimal import Decimal
from typing import Optional

from exchange.base.constants import MONETARY_DECIMAL_PLACES
from exchange.corporate_banking.integrations.converters.base_statement_converter import BaseStatementConverter
from exchange.corporate_banking.models import STATEMENT_TYPE, CoBankStatement
from exchange.wallet.constants import DEPOSIT_MAX_DIGITS


class TomanStatementConverter(BaseStatementConverter):
    def convert(self) -> Optional[CoBankStatement]:
        if self.statement_data.amount is None:
            return

        if self.statement_data.amount >= Decimal(f'1e{DEPOSIT_MAX_DIGITS - MONETARY_DECIMAL_PLACES}'):
            return

        if self.statement_data.source_account and len(self.statement_data.source_account) > 25:
            return

        statement_tp = (
            STATEMENT_TYPE.deposit
            if self.statement_data.side is True
            else (STATEMENT_TYPE.withdraw if self.statement_data.side is False else STATEMENT_TYPE.unknown)
        )

        return CoBankStatement(
            amount=self.statement_data.amount,
            tp=statement_tp,
            tracing_number=self.statement_data.tracing_number,
            transaction_datetime=self.statement_data.transaction_datetime,
            payment_id=self.statement_data.payment_id,
            source_account=self.statement_data.source_account,
            source_iban=self.statement_data.source_iban,
            source_card=self.statement_data.source_card,
            provider_statement_id=str(self.statement_data.id),
            description=self.statement_data.description,
            api_response=self.statement_data.api_response,
        )
