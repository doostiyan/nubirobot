from dataclasses import dataclass
from typing import Set

from ...utils.dto import DTO, BaseDTOCreator


@dataclass
class BlockAddressesDto(DTO):
    input_addresses: Set[str]
    output_addresses: Set[str]


class BlockAddressesDTOCreator(BaseDTOCreator):
    DTO_CLASS = BlockAddressesDto
