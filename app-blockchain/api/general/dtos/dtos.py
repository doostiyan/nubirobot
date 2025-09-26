from dataclasses import dataclass, fields
from datetime import datetime
from decimal import Decimal
from typing import Optional


class Base:
    @classmethod
    def from_dict(cls, input_dict: dict) -> object:
        return cls(**input_dict)

    @classmethod
    def get_fields(cls) -> tuple:
        return fields(cls)


@dataclass
class NewBalancesV2(Base):
    address: str
    balance: str
    contract_address: str
    symbol: str
    network: str
    block_number: int
    block_timestamp: str


@dataclass
class SelectedCurrenciesBalancesRequest:
    address: str
    contract_address: str


@dataclass
class Balance(Base):
    balance: Decimal
    address: Optional[str] = None
    unconfirmed_balance: Optional[Decimal] = None
    token: Optional[str] = None
    symbol: Optional[str] = None


@dataclass
class TransferTx(Base):
    tx_hash: str
    success: bool
    from_address: str
    to_address: str
    value: Decimal
    symbol: str
    confirmations: int = 0
    block_height: Optional[int] = None
    block_hash: Optional[str] = None
    date: Optional[datetime] = None
    memo: Optional[str] = None
    tx_fee: Optional[Decimal] = None
    token: Optional[str] = None
    index: int = None
