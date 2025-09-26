from enum import IntEnum
from typing import Optional

from pydantic import BaseModel

from exchange.asset_backed_credit.models import UserService


class CardStatus(IntEnum):
    issued = 1
    active = 2
    inactive = 3


class CardDetail(BaseModel):
    status: CardStatus


class UserServiceExternalDetails(BaseModel):
    id: str
    status: Optional[UserService.Status] = None
    amount: Optional[int] = None
