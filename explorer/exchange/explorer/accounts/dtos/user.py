from dataclasses import dataclass
from typing import List

from ...authentication.dtos import APIKeyDTO, APIKeyDTOCreator
from ...utils.datetime import datetime2str
from ...utils.dto import DTO, BaseDTOCreator


@dataclass
class UserDTO(DTO):
    username: str
    first_name: str
    last_name: str
    email: str
    date_joined: str
    api_keys: List[APIKeyDTO]


class UserDTOCreator(BaseDTOCreator):
    DTO_CLASS = UserDTO

    @classmethod
    def normalize_data(cls, data: dict) -> dict:
        data = super().normalize_data(data)
        data['api_keys'] = [APIKeyDTOCreator.get_dto(api_key_data, username=api_key_data.user.username) for api_key_data
                            in data.get('api_keys') or []]
        if data.get('date_joined') is not None:
            data['date_joined'] = datetime2str(data['date_joined'])
        return data
