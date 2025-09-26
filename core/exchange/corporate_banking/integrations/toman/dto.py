from dataclasses import dataclass, fields
from typing import ClassVar, Dict, Generic, List, Optional, TypeVar


@dataclass
class AuthenticationTokenData:
    access_token: str
    expires_in: int
    token_type: str
    scope: str
    refresh_token: str


@dataclass
class PaginationItemDTO:
    pass


T = TypeVar('T', bound=PaginationItemDTO)


@dataclass
class PaginationDTO(Generic[T]):
    """
    Represents the result of paginated APIs from CoBank provider APIs
    """

    count: int
    next: Optional[str]
    previous: Optional[str]
    results: List[T]


@dataclass
class StatementItemDTO:
    """
    Represents a single statement model from the CoBank Statement API.
    """

    destination_account: int
    api_response: Dict
    id: Optional[int] = None
    amount: Optional[int] = None
    side: Optional[bool] = None
    tracing_number: Optional[str] = None
    transaction_datetime: Optional[str] = None
    created_at: Optional[str] = None
    payment_id: Optional[str] = None
    source_account: Optional[str] = None
    source_card: Optional[str] = None
    source_iban: Optional[str] = None
    is_normalized: Optional[bool] = None
    balance: Optional[int] = None
    branch_code: Optional[str] = None
    description: Optional[str] = None


@dataclass
class TransferDTO:
    """
    Represents transfer details in a refund response
    """
    uuid: str
    bank_id: int
    account: int
    account_number_source: Optional[str] = None
    iban_source: Optional[str] = None
    transfer_type: Optional[int] = None
    status: Optional[int] = None
    amount: Optional[int] = None
    iban_destination: Optional[str] = None
    account_number_destination: Optional[str] = None
    card_number_destination: Optional[str] = None
    description: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    reason: Optional[int] = None
    tracker_id: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[int] = None
    creation_type: Optional[int] = None
    bank_id_destination: Optional[int] = None
    follow_up_code: Optional[str] = None
    payment_id: Optional[str] = None
    receipt_link: Optional[str] = None
    attachment_count: Optional[int] = None
    attachments: Optional[List] = None


@dataclass
class RefundData:
    """
    Represents a complete refund response from the API
    """

    PROVIDER_STATUS_MAP: ClassVar = {
        0: 'pending',  # CREATED
        2: 'pending',  # PROCESSING
        4: 'pending',  # TRANSFER_CREATED
        6: 'completed',  # SUCCESS
        8: 'invalid',  # FAILED
    }

    id: int
    transfer: TransferDTO
    transfer_id: str
    statement_id: int
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    account: Optional[int] = None
    created_by: Optional[int] = None
    partner: Optional[int] = None
    api_response: Optional[dict] = None

    @classmethod
    def from_data(cls, data: dict):
        api_response = data.copy()
        transfer_id = ''

        if api_response.get('transfer'):
            transfer_id = api_response.get('transfer', {}).get('uuid', '')
            transfer_dto_fields = {
                k: v for k, v in api_response.get('transfer', {}).items() if k in [f.name for f in fields(TransferDTO)]
            }
            transfer = TransferDTO(**transfer_dto_fields)
            api_response['transfer'] = transfer

        provider_status = api_response.get('status')
        status = cls.PROVIDER_STATUS_MAP.get(provider_status, 'unknown')

        if 'status' in api_response:
            del api_response['status']

        return cls(api_response=data, transfer_id=transfer_id, status=status, **api_response)
