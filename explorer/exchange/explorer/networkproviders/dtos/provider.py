from dataclasses import dataclass

from ...utils.dto import DTO, BaseDTOCreator


@dataclass
class CheckProviderResultDto(DTO):
    is_healthy: bool
    block_head: int
    message: str = None


class CheckProviderResultDtoCreator(BaseDTOCreator):
    DTO_CLASS = CheckProviderResultDto


@dataclass
class ProviderData(DTO):
    provider_name: str
    interface_name: str
    base_url: str = None


@dataclass
class ProviderDataCreator(BaseDTOCreator):
    DTO_CLASS = ProviderData
