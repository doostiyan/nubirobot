from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class VerificationAPIError(ValueError):
    code: str
    status: Optional[int] = None


class FinnotechAPIError(VerificationAPIError):
    pass


class JibitAPIError(VerificationAPIError):
    pass


@dataclass
class VerificationError(Exception):
    api_response: Any
    provider: str
    msg: Optional[str] = None


class InvalidNationalCode(VerificationError):
    pass


class InvalidBirthDate(VerificationError):
    pass


class InvalidFirstName(VerificationError):
    pass


class InvalidLastName(VerificationError):
    pass


class InvalidFullName(VerificationError):
    pass


class InvalidFatherName(VerificationError):
    pass


class InvalidMobile(VerificationError):
    pass


class UnknownLivingStatus(VerificationError):
    pass


class DeadLivingStatus(VerificationError):
    pass


class RateLimited(Exception):
    pass


class InvalidIBAN(VerificationError):
    pass


class InactiveIBAN(VerificationError):
    pass


class MismatchedIBAN(VerificationError):
    pass


class InvalidCard(VerificationError):
    pass


class InactiveCard(VerificationError):
    pass


class MismatchedCard(VerificationError):
    pass


class UnknownCardQueryError(VerificationError):
    pass


class NotFound(VerificationError):
    pass


@dataclass
class CardToIbanError(VerificationError):
    msg: str
