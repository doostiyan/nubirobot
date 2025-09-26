from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from exchange.corporate_banking.helpers import (
    get_nobitex_bank_choice_from_jibit_name,
    get_nobitex_bank_choice_from_toman_choice,
)
from exchange.corporate_banking.integrations.toman.dto import PaginationItemDTO
from exchange.corporate_banking.models.constants import COBANK_PROVIDER


@dataclass
class AccountData(PaginationItemDTO):
    """
    Represents a single account model from the CoBank Accounts API.
    """

    id: str
    iban: str
    account_number: str
    account_owner: str
    active: bool
    opening_date: datetime
    balance: Decimal
    details: dict
    provider: int
    bank_id: Optional[int]

    @classmethod
    def from_jibit(cls, data: dict) -> 'AccountData':
        return cls(
            id=str(data['id']) if data['id'] is not None else None,
            active=data['active'],
            bank_id=get_nobitex_bank_choice_from_jibit_name(data['bank']),
            balance=data.get('balance', Decimal(0)),
            account_number=data['accountNumber'],
            iban=data['iban'],
            account_owner=data['ownerFirstName'] + ' ' + data['ownerLastName'],
            opening_date=datetime.fromisoformat(data['createdAt'].replace('Z', '+00:00')),
            provider=COBANK_PROVIDER.jibit,
            details=data,
        )

    @classmethod
    def from_toman(cls, data: dict) -> 'AccountData':
        return cls(
            id=str(data['id']) if data['id'] is not None else None,
            active=data['active'],
            bank_id=get_nobitex_bank_choice_from_toman_choice(data['bank_id']),
            balance=data['balance'],
            account_number=data['account_number'],
            iban=data['iban'],
            account_owner=data['account_owner'],
            opening_date=data['opening_date'],
            provider=COBANK_PROVIDER.toman,
            details=data,
        )
