import decimal
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from requests import Response

from exchange.base.parsers import parse_choices, parse_utc_timestamp_ms


@dataclass
class DirectDebitFaraboomRequest:
    trace_id: str
    contract_id: str
    amount: decimal.Decimal
    description: str
    transaction_time: datetime
    fee: decimal.Decimal


@dataclass
class DirectDepositDetailFaraboomResponse:
    reference_id: str
    trace_id: str
    amount: decimal.Decimal
    transaction_time: datetime
    status: str
    transaction_detail_type: str

    def __dict__(self) -> dict:
        return {
                'reference_id': self.reference_id,
                'trace_id': self.trace_id,
                'amount': self.amount,
                'transaction_time': self.transaction_time,
                'status': self.status,
                'transaction_detail_type': self.transaction_detail_type,
            }


@dataclass
class DirectDepositFaraboomResponse:
    reference_id: str
    trace_id: str
    transaction_amount: decimal.Decimal
    transaction_time: datetime
    batch_id: Optional[int]
    commission_amount: decimal.Decimal
    status: str
    details: List[DirectDepositDetailFaraboomResponse]

    def prepare_for_update(self) -> dict:
        details = []
        for detail in self.details:
            details.append(detail.__dict__())
        return {
                'reference_id': self.reference_id,
                'trace_id': self.trace_id,
                'amount': self.transaction_amount,
                'batch_id': self.batch_id,
                'details': details,
            }


@dataclass
class DirectDebitAuthData:
    client_id: str
    client_secret: str
    app_key: str


def get_deposit_response_object(response: Response) -> DirectDepositFaraboomResponse:
    output = response.json()
    details = []
    for detail in output.get('details'):
        details.append(
            DirectDepositDetailFaraboomResponse(
                amount=detail.get('amount'),
                reference_id=detail.get('reference_id'),
                trace_id=detail.get('trace_id'),
                transaction_time=detail.get('transaction_time'),
                transaction_detail_type=detail.get('transaction_detail_type'),
                status=detail.get('status'),
            ),
        )
    return DirectDepositFaraboomResponse(
        reference_id=output.get('reference_id'),
        transaction_amount=Decimal(output.get('transaction_amount')),
        transaction_time=output.get('transaction_time'),
        status=output.get('status'),
        trace_id=output.get('trace_id'),
        batch_id=output.get('batch_id', ''),
        commission_amount=output.get('commission_amount'),
        details=details,
    )


@dataclass
class DirectDepositTraceObject:
    currency: str
    description: str
    destination_bank: str
    destination_deposit: str
    source_bank: str
    source_deposit: str
    transaction_type: str
    reference_id: str
    trace_id: str
    transaction_amount: int
    transaction_time: int
    commission_amount: int
    status: str
    batch_id: Optional[str] = ''

    def prepare_for_update(self) -> dict:
        return {
            'reference_id': self.reference_id,
            'trace_id': self.trace_id,
            'amount': self.transaction_amount,
            'batch_id': self.batch_id,
            'deposited_at': parse_utc_timestamp_ms(self.transaction_time),
            'created_at': parse_utc_timestamp_ms(self.transaction_time),
        }

    def prepare_for_create(self) -> dict:
        from exchange.direct_debit.models import DailyDirectDeposit

        return {
            'transaction_amount': self.transaction_amount,
            'description': self.description,
            'reference_id': self.reference_id,
            'trace_id': self.trace_id,
            'transaction_type': self.transaction_type,
            'destination_bank': self.destination_bank,
            'source_bank': self.source_bank,
            'server_date': parse_utc_timestamp_ms(self.transaction_time),
            'client_date': parse_utc_timestamp_ms(self.transaction_time),
            'status': parse_choices(DailyDirectDeposit.STATUS, self.status),
            'contract_id': None,
            'deposit': None,
        }


def get_deposit_dto_from_response(response: Response) -> DirectDepositTraceObject:
    json_response = response.json()
    return DirectDepositTraceObject(
        currency=json_response.get('currency'),
        description=json_response.get('description'),
        destination_bank=json_response.get('destination_bank'),
        destination_deposit=json_response.get('destination_deposit'),
        source_bank=json_response.get('source_bank'),
        source_deposit=json_response.get('source_deposit'),
        transaction_type=json_response.get('transaction_type'),
        reference_id=json_response.get('reference_id') or '',
        trace_id=json_response.get('trace_id'),
        transaction_amount=json_response.get('transaction_amount'),
        transaction_time=json_response.get('transaction_time'),
        batch_id=json_response.get('batch_id', ''),
        commission_amount=json_response.get('commission_amount'),
        status=json_response.get('status').lower(),
    )


def get_deposit_dto_from_object(obj: 'DailyDirectDeposit') -> DirectDepositTraceObject:
    return DirectDepositTraceObject(
        currency='IRR',
        description=obj.description,
        destination_bank='',
        destination_deposit='',
        source_bank='',
        source_deposit='',
        transaction_type='NORMAL',
        reference_id=obj.reference_id,
        trace_id=obj.trace_id,
        transaction_amount=obj.transaction_amount,
        transaction_time=int(obj.server_date.timestamp() * 1000),
        batch_id='',
        commission_amount=0,
        status=next(
            (key for key, value in obj.STATUS._identifier_map.items() if value == obj.status),
            'unknown',
        ).lower(),
    )
