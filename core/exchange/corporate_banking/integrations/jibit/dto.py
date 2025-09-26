from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from exchange.base.parsers import parse_iso_date


@dataclass
class AuthenticationTokenData:
    accessToken: str
    refreshToken: str
    scopes: List[str]


BARDASHT_TYPES = Literal[
    'BARDASHT_UNKNOWN',
    'BARDASHT_JIBIT_COLLECT',
    'BARDASHT_NAGHDI',
    'BARDASHT_TRANSFER_INTERNAL',
    'BARDASHT_TRANSFER_ACH',
    'BARDASHT_TRANSFER_ACH_BATCH',
    'BARDASHT_TRANSFER_RTGS',
    'BARDASHT_TRANSFER_POL',
    'BARDASHT_FEE',
    'BARDASHT_ESLAHI',
]

VARIZ_TYPES = Literal[
    'VARIZ_UNKNOWN',
    'VARIZ_BANK_CHECK',
    'VARIZ_NAGHDI',
    'VARIZ_INTERNAL',
    'VARIZ_CARD',
    'VARIZ_ACH',
    'VARIZ_RTGS',
    'VARIZ_POL',
    'VARIZ_SODE_HESAB',
    'VARIZ_ESLAHI',
    'VARIZ_SHAPARAK_IPG_SETTLEMENT',
]

RECORD_TYPES = Union[BARDASHT_TYPES, VARIZ_TYPES]

MERCHANT_VERIFICATION_STATUS = Literal['TO_BE_DECIDED', 'REJECTED', 'VERIFIED', 'SYSTEM_REVIEW']
REFUND_TYPE = Literal['FULL_REFUND', 'PARTIAL_REFUND']
TRANSFER_RECORD_TYPE = Literal['PRIME', 'ARCHIVE']
TRANSFER_STATE = Literal[
    'RECEIVED',
    'SOURCE_PROCESSING',
    'DESTINATION_PROCESSING',
    'TRANSFERRED',
    'FAILED',
    'TRANSFERRED_REVERTED',
    'FAILED_WRONG',
]
REQUEST_CHANNEL = Literal['PANEL', 'API', 'SYSTEM']
TRANSFER_TYPE = Literal['SETTLEMENT', 'REFUND', 'IPG_REFUND', 'CASH_MANAGEMENT']


@dataclass
class StatementItemDTO:
    destinationAccount: int
    referenceNumber: str
    bankReferenceNumber: str
    bankTransactionId: str
    timestamp: str
    sourceIban: str
    apiResponse: Dict[str, Any]
    destinationIban: Optional[str] = None
    accountIban: Optional[str] = None
    sourceIdentifier: Optional[str] = None
    destinationIdentifier: Optional[str] = None
    balance: Optional[int] = None
    debitAmount: Optional[int] = None
    creditAmount: Optional[int] = None
    rawData: Optional[str] = None
    payId: Optional[str] = None
    recordType: Optional[RECORD_TYPES] = None
    merchantVerificationStatus: Optional[MERCHANT_VERIFICATION_STATUS] = None
    kytStatus: Optional[str] = None
    refundType: Optional[REFUND_TYPE] = None
    refundTrackId: Optional[str] = None
    createdAt: Optional[str] = None


@dataclass
class CardDTO:
    id: int
    cardNumber: str
    iban: str
    active: bool


@dataclass
class TransferItemDTO:
    referenceNumber: str
    bankReferenceNumber: str
    failReason: str
    trackId: str
    recordType: TRANSFER_RECORD_TYPE
    sourceAccountIban: str
    destinationIban: str
    destinationAccountNumber: str
    destinationFirstName: str
    destinationLastName: str
    amount: int
    payId: str
    transferType: str
    state: TRANSFER_STATE
    lastSubmitSuccessAt: Optional[datetime]
    createdAt: Optional[datetime]
    updatedAt: Optional[datetime]


@dataclass
class TransferDTO:
    referenceNumber: str
    trackId: str
    ownerCode: str
    requestChannel: REQUEST_CHANNEL
    type: TRANSFER_TYPE
    sourceIban: str
    destinationIban: str
    totalAmount: int
    primeCount: int
    createdAt: Optional[datetime]
    updatedAt: Optional[datetime]
    records: List[TransferItemDTO]

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> 'TransferDTO':
        """Create TransferDTO from API response data with proper error handling."""
        if not isinstance(data, dict):
            raise ValueError('Data must be a dictionary')

        records = []
        for rec in data.get('records', []):
            if not isinstance(rec, dict):
                continue

            last_submit_success_at = None
            created_at = None
            updated_at = None

            try:
                if rec.get('lastSubmitSuccessAt'):
                    last_submit_success_at = parse_iso_date(rec['lastSubmitSuccessAt'])
            except (ValueError, TypeError):
                pass

            try:
                if rec.get('createdAt'):
                    created_at = parse_iso_date(rec['createdAt'])
            except (ValueError, TypeError):
                pass

            try:
                if rec.get('updatedAt'):
                    updated_at = parse_iso_date(rec['updatedAt'])
            except (ValueError, TypeError):
                pass

            records.append(
                TransferItemDTO(
                    referenceNumber=rec.get('referenceNumber', ''),
                    bankReferenceNumber=rec.get('bankReferenceNumber', ''),
                    failReason=rec.get('failReason', ''),
                    trackId=rec.get('trackId', ''),
                    recordType=rec.get('recordType', 'PRIME'),
                    sourceAccountIban=rec.get('sourceAccountIban', ''),
                    destinationIban=rec.get('destinationIban', ''),
                    destinationAccountNumber=rec.get('destinationAccountNumber', ''),
                    destinationFirstName=rec.get('destinationFirstName', ''),
                    destinationLastName=rec.get('destinationLastName', ''),
                    amount=rec.get('amount', 0),
                    payId=rec.get('payId', ''),
                    transferType=rec.get('transferType', ''),
                    state=rec.get('state', 'RECEIVED'),
                    lastSubmitSuccessAt=last_submit_success_at,
                    createdAt=created_at,
                    updatedAt=updated_at,
                )
            )

        main_created_at = None
        main_updated_at = None

        try:
            if data.get('createdAt'):
                main_created_at = parse_iso_date(data['createdAt'])
        except (ValueError, TypeError):
            pass

        try:
            if data.get('updatedAt'):
                main_updated_at = parse_iso_date(data['updatedAt'])
        except (ValueError, TypeError):
            pass

        return cls(
            referenceNumber=data.get('referenceNumber', ''),
            trackId=data.get('trackId', ''),
            ownerCode=data.get('ownerCode', ''),
            requestChannel=data.get('requestChannel', 'API'),
            type=data.get('type', 'REFUND'),
            sourceIban=data.get('sourceIban', ''),
            destinationIban=data.get('destinationIban', ''),
            totalAmount=data.get('totalAmount', 0),
            primeCount=data.get('primeCount', 0),
            createdAt=main_created_at,
            updatedAt=main_updated_at,
            records=records,
        )
