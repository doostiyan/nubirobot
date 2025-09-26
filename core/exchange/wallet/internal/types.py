from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from pydantic import UUID4, BaseModel, Field, field_validator

from exchange.base.api import ParseError
from exchange.base.constants import MONETARY_DECIMAL_PLACES
from exchange.base.parsers import parse_choices, parse_currency
from exchange.wallet.constants import TRANSACTION_MAX, TRANSACTION_MAX_DIGITS
from exchange.wallet.internal.exceptions import TransactionException
from exchange.wallet.models import Transaction, Wallet


@dataclass
class TransactionResult:
    tx: Optional[Transaction] = None
    error: Optional[TransactionException] = None


class TransactionInput(BaseModel):
    # wallet data
    uid: UUID4
    wallet_type: str
    currency: str

    amount: Decimal = Field(
        max_digits=TRANSACTION_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
        ge=-TRANSACTION_MAX,
        le=TRANSACTION_MAX,
        allow_inf_nan=False,
    )

    description: str = Field(min_length=1, max_length=256)
    tp: str
    ref_module: Optional[str] = None
    ref_id: Optional[int] = None

    @property
    def wallet_key(self):
        return f'{self.uid}-{self.int_currency}-{self.int_wallet_type}'

    @field_validator('wallet_type')
    @classmethod
    def wallet_type_validator(cls, v: str) -> str:
        try:
            parse_choices(Wallet.WALLET_TYPE, v, required=True)
        except ParseError as e:
            raise ValueError(f'Invalid wallet type: {v}') from e
        return v

    @field_validator('tp')
    @classmethod
    def tp_validator(cls, v: str) -> str:
        try:
            parse_choices(Transaction.TYPE, v, required=True)
        except ParseError as e:
            raise ValueError(f'Invalid tp: {v}') from e
        return v

    @field_validator('currency')
    @classmethod
    def currency_validator(cls, v: str) -> str:
        try:
            parse_currency(v, required=True)
        except ParseError as e:
            raise ValueError(f'Invalid currency: {v}') from e
        return v

    @field_validator('ref_module')
    @classmethod
    def ref_module_validator(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in Transaction.REF_MODULES:
            raise ValueError(f'Invalid ref_module: {v}')
        return v

    @property
    def int_wallet_type(self):
        return getattr(Wallet.WALLET_TYPE, self.wallet_type)

    @property
    def int_tp(self):
        return getattr(Transaction.TYPE, self.tp)

    @property
    def int_currency(self):
        return parse_currency(self.currency, required=True)
