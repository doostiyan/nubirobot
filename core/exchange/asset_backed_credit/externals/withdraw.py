from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from exchange.asset_backed_credit.exceptions import FeatureUnavailable, InternalAPIError
from exchange.asset_backed_credit.externals.base import NOBITEX_BASE_URL, InternalAPI
from exchange.base.decorators import measure_time_cm
from exchange.base.internal.idempotency import IDEMPOTENCY_HEADER
from exchange.base.logging import report_event
from exchange.base.models import Settings


class RialWithdrawRequestSchema(BaseModel):
    user_id: UUID = Field(alias='userId')
    amount: int
    iban: str = Field(alias='shabaNumber')
    explanation: str

    model_config = ConfigDict(
        populate_by_name=True,
    )


class RialWithdrawResponseSchema(BaseModel):
    id: int


class RialWithdrawRequestAPI(InternalAPI):
    url = f'{NOBITEX_BASE_URL}/internal/wallets/withdraw-rial'
    method = 'post'
    need_auth = True
    service_name = 'rial-withdraw-request'
    endpoint_key = 'rialWithdrawRequest'
    error_message = 'RialWithdrawRequest'

    @measure_time_cm(metric='abc_rial_withdraw_request')
    def request(self, data: RialWithdrawRequestSchema, idempotency: UUID) -> RialWithdrawResponseSchema:
        if not Settings.get_flag('abc_use_rial_withdraw_request_internal_api'):
            raise FeatureUnavailable

        json_data = data.model_dump(mode='json', by_alias=True)
        try:
            response = self._request(json=json_data, headers={IDEMPOTENCY_HEADER: str(idempotency)})
            result = self.jsonify_response_data(response)
            return RialWithdrawResponseSchema(id=result['id'])
        except Exception as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise InternalAPIError(f'{self.error_message}: rial withdraw request error') from e
