from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_pascal


class GetRequestDetailSchema(BaseModel):
    status: int = Field(alias='statusId')


class GetRequestResponseSchema(BaseModel):
    is_success: bool
    error_code: Optional[str]
    message: str
    detail: GetRequestDetailSchema = Field(alias='GetRequestDetail')

    model_config = ConfigDict(
        alias_generator=to_pascal,
        populate_by_name=True,
    )


class IssueChildCardSchema(BaseModel):
    birth_cert_no: str = Field(alias='BirthCertificateNumber')
    national_code: str = Field(alias='NationalCode')
    first_name: str = Field(alias='PersianFirstName')
    last_name: str = Field(alias='PersianLastName')
    first_name_en: str = Field(alias='LatinFirstName')
    last_name_en: str = Field(alias='LatinLastName')
    gender: int = Field(alias='GenderTypeCode')
    father_name: str = Field(alias='FatherName')
    birth_date: str = Field(alias='BirthDate')
    cell_number: str = Field(alias='CellNumber')
    address: str = Field(alias='Address')
    zip_code: str = Field(alias='ZipCode')

    model_config = ConfigDict(
        populate_by_name=True,
    )


class IssueChildCardResponseSchema(BaseModel):
    is_success: bool
    error_code: Optional[int]
    message: str
    card_request_id: Optional[int]

    model_config = ConfigDict(
        alias_generator=to_pascal,
        populate_by_name=True,
    )


class ProvinceSchema(BaseModel):
    id: int = Field(alias='Id')
    title: str = Field(alias='PersianTitle')


class CitySchema(BaseModel):
    id: int = Field(alias='Id')
    province_id: int = Field(alias='ProvinceId')
    title: str = Field(alias='PersianTitle')
