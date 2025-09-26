import pytz
from datetime import datetime
from dataclasses import dataclass
from typing import Union

from django.conf import settings

from exchange.explorer.utils.dto import BaseDTOCreator, DTO
from exchange.explorer.utils.datetime import datetime2str


@dataclass
class JWTAuthDTO(DTO):
    refresh: str
    access: str


class JWTAuthDTOCreator(BaseDTOCreator):
    DTO_CLASS = JWTAuthDTO


