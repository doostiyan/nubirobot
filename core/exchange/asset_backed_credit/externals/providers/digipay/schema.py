from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class Status(str, Enum):
    ACTIVATED = 'ACTIVATED'
    IN_PROGRESS = 'IN_PROGRESS'
    FAILED = 'FAILED'
    IN_CLOSURE = 'IN_CLOSURE'
    CLOSED = 'CLOSED'
    BLOCKED = 'BLOCKED'


class ResultSchema(BaseModel):
    title: Optional[str] = None
    status: int
    message: Optional[str] = None
    level: Optional[str] = None


class ResponseSchema(BaseModel):
    tracking_code: Optional[str] = None
    status: Optional[Status] = None
    allocated_amount: Optional[int] = None
    result: ResultSchema

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class StoreSchema(BaseModel):
    title: str
    url: str

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class StoresSearchResponseSchema(BaseModel):
    result: ResultSchema
    stores: Optional[List[StoreSchema]] = None
    total_elements: Optional[int] = None
    total_pages: Optional[int] = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )
