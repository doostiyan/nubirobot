import enum
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict


class VerificationAPIProviders(Enum):
    FINNOTECH = 'finnotech'
    JIBIT = 'jibit'


@dataclass
class IdentityVerificationClientResult:
    provider: VerificationAPIProviders
    api_response: Any

    first_name_similarity: Optional[int] = None
    last_name_similarity: Optional[int] = None
    full_name_similarity: Optional[int] = None
    father_name_similarity: Optional[int] = None


class IdentityVerificationResult(TypedDict):
    result: bool
    confidence: int
    message: str
    apiresponse: str
    err_code: Optional[str]


class MobileOwnerVerificationResult(TypedDict):
    result: bool
    message: str
    apiresponse: str
    err_code: Optional[str]


class IBANOwnerVerificationResult(TypedDict):
    result: bool
    confidence: int
    message: str
    apiresponse: Dict
    err_code: Optional[str]


class BankCardOwnerVerificationResult(TypedDict):
    result: bool
    confidence: int
    message: str
    apiresponse: Dict
    err_code: Optional[str]


@dataclass
class CardToIbanResult:
    api_response: Dict
    iban: Optional[str] = None
    deposit: Optional[str] = None
    error_message: Optional[str] = None
    err_code: str = ''

    @property
    def successful(self):
        return self.error_message is None

    def get(self, name: str) -> Any:
        return getattr(self, name, None)


@dataclass
class CardToIbanAPICallResultV2:
    provider: VerificationAPIProviders
    api_response: Any

    deposit: str
    iban: str
    owners: List[str]


class DepositStatusInIbanInquiryEnum(enum.Enum):
    ACTIVE = 'ACTIVE'
    BLOCK_WITH_DEPOSIT = 'BLOCK_WITH_DEPOSIT'
    BLOCK_WITHOUT_DEPOSIT = 'BLOCK_WITHOUT_DEPOSIT'
    IDLE = 'IDLE'
    UNKNOWN = 'UNKNOWN'


@dataclass
class IbanInquiry:
    provider: VerificationAPIProviders
    bank: str
    deposit_number: str
    iban: str
    deposit_status: str
