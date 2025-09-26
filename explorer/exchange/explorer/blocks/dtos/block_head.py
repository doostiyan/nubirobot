from dataclasses import dataclass

from ...utils.dto import DTO, BaseDTOCreator


@dataclass
class BlockheadDTO(DTO):
    block_head: int


class BlockHeadDTOCreator(BaseDTOCreator):
    DTO_CLASS = BlockheadDTO
