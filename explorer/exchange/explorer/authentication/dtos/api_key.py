from dataclasses import dataclass
from datetime import datetime
from typing import Union

import pytz
from django.conf import settings

from ...utils.datetime import datetime2str
from ...utils.dto import DTO, BaseDTOCreator


@dataclass
class APIKeyDTO(DTO):
    name: str
    username: str
    prefix: str
    created: str
    rate: str
    expiry_date: Union[str, None]
    revoked: bool


class APIKeyDTOCreator(BaseDTOCreator):
    DTO_CLASS = APIKeyDTO

    @classmethod
    def normalize_data(cls, data: dict) -> dict:
        data = super().normalize_data(data)
        if data.get('created') is not None:
            data['created'] = datetime2str(data['created'])
        if data.get('expiry_date') is not None:
            data['expiry_date'] = datetime2str(data['expiry_date'])
        return data
