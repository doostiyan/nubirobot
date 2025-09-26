from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from dateutil import parser
from pydantic import UUID4, BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic.alias_generators import to_camel

from exchange.asset_backed_credit.exceptions import ClientError, FeatureUnavailable, InternalAPIError
from exchange.asset_backed_credit.externals.base import NOBITEX_BASE_URL, InternalAPI
from exchange.asset_backed_credit.types import TransactionInput, WalletType
from exchange.base.decorators import measure_time_cm
from exchange.base.internal.idempotency import IDEMPOTENCY_HEADER
from exchange.base.logging import report_event
from exchange.base.models import Settings


class TransactionProvider:
    @classmethod
    def create_transactions(
        cls, input_transactions: List[TransactionInput], idempotency: str
    ) -> List['ExchangeTransactionSchema']:
        if not input_transactions:
            raise ValueError

        data = [
            ExchangeTransactionRequest(
                uid=trx.user_id,
                wallet_type=WalletType.CREDIT
                if trx.exchange_wallet_type == WalletType.COLLATERAL
                else trx.exchange_wallet_type,
                currency=trx.currency,
                amount=trx.amount,
                description=trx.description,
                tp=ExchangeTransactionType.ABC,  # FIXME: maybe other types too?!!
                ref_module=None,  # FIXME: ref
                ref_id=None,  # FIXME: ref
            )
            for trx in input_transactions
            if trx.exchange_wallet_type
        ]
        return BatchTransactionCreateAPI().request(data, idempotency)


class ExchangeTransactionType(str, Enum):
    ABC = 'asset_backed_credit'


class ExchangeTransactionRefModuleType(str, Enum):
    user_settlement = 'AssetBackedCreditUserSettlement'
    provider_settlement = 'AssetBackedCreditProviderSettlement'
    insurance_settlement = 'AssetBackedCreditInsuranceSettlement'


class ExchangeTransactionRequest(BaseModel):
    uid: UUID4
    wallet_type: WalletType
    currency: str
    amount: Decimal
    description: str = Field(min_length=1, max_length=256)
    tp: ExchangeTransactionType
    ref_module: ExchangeTransactionRefModuleType
    ref_id: int


class ExchangeTransactionItemSchema(BaseModel):
    amount: Decimal
    balance: Decimal
    created_at: datetime
    currency: str
    description: str
    id: int
    ref_id: int
    ref_module: ExchangeTransactionRefModuleType
    type: ExchangeTransactionType

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    @field_validator("created_at", mode='before')
    @classmethod
    def parse_returned_datetime(cls, v: str) -> datetime:
        parsed = parser.parse(v)
        if not parsed:
            raise ValueError(f"Invalid datetime string: {v}")
        return parsed


class ExchangeTransactionSchema(BaseModel):
    error: Optional[str] = None
    transaction: ExchangeTransactionItemSchema


class BatchTransactionCreateAPI(InternalAPI):
    url = f'{NOBITEX_BASE_URL}/internal/transactions/batch-create'
    method = 'post'
    need_auth = True
    service_name = 'transaction'
    endpoint_key = 'transactionBatchCreate'
    error_message = 'TransactionBatchCreate'

    @measure_time_cm(metric='abc_transaction_batchCreate')
    def request(self, data: List[ExchangeTransactionRequest], idempotency: str) -> List[ExchangeTransactionSchema]:
        if not Settings.get_flag('abc_use_transaction_batch_create_internal_api'):
            raise FeatureUnavailable

        try:
            response = self._request(json=self._prepare_request_data(data), headers={IDEMPOTENCY_HEADER: idempotency})
            return self._validate_response_data(self.jsonify_response_data(response))
        except (TypeError, ValueError, ClientError, ValidationError) as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise InternalAPIError(f'{self.error_message}: transaction batch create failure') from e

    @classmethod
    def _prepare_request_data(cls, data: List[ExchangeTransactionRequest]) -> List[Dict]:
        return [d.model_dump(mode='json') for d in data]

    @classmethod
    def _validate_response_data(cls, data: List[Dict]) -> List[ExchangeTransactionSchema]:
        validated_data = []
        errors = []
        for item in data:
            error = item.get('error')
            if error is not None:
                errors.append(error)
            transaction = item.get('tx')
            validated_data.append(
                ExchangeTransactionSchema(
                    error=error, transaction=ExchangeTransactionItemSchema.model_validate(transaction)
                )
            )

        if errors:
            raise ValidationError(
                f'Error on internal transactions: {str(errors)}',
            )
        return validated_data
