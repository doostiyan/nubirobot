from pydantic import BaseModel


class DebitCardUserInfoSchema(BaseModel):
    first_name: str
    last_name: str
    first_name_en: str
    last_name_en: str
    national_code: str
    birth_cert_no: str
    mobile: str
    father_name: str
    gender: int
    birth_date: str
    postal_code: str
    province: str
    city: str
    address: str
    color: int
