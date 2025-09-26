from abc import ABC, abstractmethod
from typing import Optional

from exchange.corporate_banking.models import CoBankStatement


class BaseStatementConverter(ABC):
    def __init__(self, statement_data):
        self.statement_data = statement_data

    @abstractmethod
    def convert(self) -> Optional[CoBankStatement]:
        pass
