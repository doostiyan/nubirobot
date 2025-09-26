from dataclasses import dataclass
from typing import List

from ...utils.dto import DTO, BaseDTOCreator
from exchange.blockchain.api.general.dtos import TransferTx


@dataclass
class BlockInfoDTO(DTO):
    latest_processed_block: int
    transactions: List[TransferTx]


class BlockInfoDTOCreator(BaseDTOCreator):
    DTO_CLASS = BlockInfoDTO
