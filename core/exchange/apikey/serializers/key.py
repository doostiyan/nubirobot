import datetime
import typing

import pydantic
from pydantic.networks import IPvAnyAddress

from exchange.apikey.models import Permission


class KeyRequest(pydantic.BaseModel):
    name: str = pydantic.Field(max_length=1024)
    description: str = pydantic.Field(default='', max_length=1000)
    permissions: Permission = pydantic.Field()
    ip_addresses_whitelist: typing.List[IPvAnyAddress] = pydantic.Field(
        alias='ipAddressesWhitelist',
        default_factory=list,
    )
    expiration_date: typing.Optional[datetime.datetime] = pydantic.Field(alias='expirationDate', default=None)

    @pydantic.field_validator('permissions', mode='before')
    @classmethod
    def set_permissions(cls, v: typing.Union[str, Permission]) -> Permission:
        if isinstance(v, str):
            try:
                return Permission.parse(v)
            except KeyError as e:
                raise ValueError('permissions are not parsable') from e
        return v

    @pydantic.field_serializer('permissions')
    def get_permissions(self, v: Permission, _) -> str:
        return str(v)


class KeySerializer(KeyRequest):
    model_config = pydantic.ConfigDict(populate_by_name=True)

    key: str = pydantic.Field()
    created_at: datetime.datetime = pydantic.Field(alias='createdAt')
    updated_at: datetime.datetime = pydantic.Field(alias='updatedAt')


class KeyCreationResponse(pydantic.BaseModel):
    status: str
    private_key: str = pydantic.Field(serialization_alias='privateKey')
    key: KeySerializer


class KeyListResponse(pydantic.BaseModel):
    status: str
    keys: typing.List[KeySerializer]


class KeyUpdateRequest(pydantic.BaseModel):
    name: typing.Optional[str] = pydantic.Field(default=None, max_length=1024)
    description: typing.Optional[str] = pydantic.Field(default=None, max_length=1000)
    ip_addresses_whitelist: typing.Optional[typing.List[IPvAnyAddress]] = pydantic.Field(
        validation_alias='ipAddressesWhitelist',
        default=None,
    )


class KeyUpdateResponse(pydantic.BaseModel):
    status: str
    key: KeySerializer
