from typing import Optional, List

from pydantic import BaseModel

class Transaction(BaseModel):
    tx_hash: str
    success: bool
    value: str
    symbol: str
    block_height: Optional[int] = None
    date: Optional[str] = None
    created_at: str
    network: str
    from_address: Optional[str] = None
    to_address: Optional[str] = None

class NewBlockchainTransactionsEvent(BaseModel):
    transactions: List[Transaction]