from dataclasses import dataclass
from decimal import Decimal

from exchange.explorer.utils.dto import DTO, BaseDTOCreator


@dataclass
class WalletBalanceDTO(DTO):
    address: str
    balance: Decimal
    contract_address: str
    symbol: str
    network: str
    block_number: int

class WalletBalanceDTOCreator(BaseDTOCreator):
    DTO_CLASS = WalletBalanceDTO
