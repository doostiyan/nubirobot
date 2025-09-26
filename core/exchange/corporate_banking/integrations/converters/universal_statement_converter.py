from typing import Optional

from exchange.corporate_banking.integrations.jibit.converters import JibitStatementConverter
from exchange.corporate_banking.integrations.jibit.dto import StatementItemDTO as JibitStatementItemDTO
from exchange.corporate_banking.integrations.toman.converters import TomanStatementConverter
from exchange.corporate_banking.integrations.toman.dto import StatementItemDTO as TomanStatementItemDTO
from exchange.corporate_banking.models import CoBankStatement


class UniversalStatementConverter:
    def __init__(self, statement_data):
        self.statement_data = statement_data

    def convert(self) -> Optional[CoBankStatement]:
        if isinstance(self.statement_data, JibitStatementItemDTO):
            return JibitStatementConverter(self.statement_data).convert()
        elif isinstance(self.statement_data, TomanStatementItemDTO):
            return TomanStatementConverter(self.statement_data).convert()
        else:
            raise ValueError(f'No converter found for DTO type {type(self.statement_data)}')
