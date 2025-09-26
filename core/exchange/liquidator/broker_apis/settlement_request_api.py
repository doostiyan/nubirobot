from enum import Enum

from exchange.base.models import get_currency_codename
from exchange.liquidator.errors import (
    BrokerAPIError,
    BrokerAPIError4XX,
    DuplicatedOrderError,
    InvalidAPIInputError,
    SmallOrderError,
)
from exchange.liquidator.models import Liquidation

from .base import BrokerBaseAPI


class SettlementRequestErrorEnum(Enum):
    DUPLICATED_ORDER = 'duplicate clientId'
    SMALL_ORDER = 'small order amount'


class SettlementRequest(BrokerBaseAPI):
    url = '/liquidation/liquidation'
    method = 'post'
    ttl = 30 * 1000  # in milliseconds
    metric_name = 'brokerSettlementRequests'
    acceptable_status = ('created', 'open')
    retry_limit = 2

    def request(self, liquidation: Liquidation):
        if liquidation.amount <= 0:
            raise InvalidAPIInputError('Amount should be greater than zero.')

        if liquidation.primary_price and liquidation.primary_price <= 0:
            raise InvalidAPIInputError('Price should be greater than zero.')

        data = {
            'clientId': liquidation.tracking_id,
            'baseCurrency': get_currency_codename(liquidation.src_currency),
            'quoteCurrency': get_currency_codename(liquidation.dst_currency),
            'side': 'sell' if liquidation.is_sell else 'buy',
            'amount': str(liquidation.amount),
            'type': 'market',
            'ttl': self.ttl,
        }

        try:
            result = self._request(json=data)
        except BrokerAPIError4XX as e:
            msg_exception_mapper = {
                SettlementRequestErrorEnum.DUPLICATED_ORDER.value: DuplicatedOrderError,
                SettlementRequestErrorEnum.SMALL_ORDER.value: SmallOrderError,
            }
            exception_class = msg_exception_mapper.get(str(e))
            if exception_class:
                raise exception_class() from e
            raise

        settlement_id = result.get('liquidationId')
        if result.get('status') not in self.acceptable_status or settlement_id is None:
            raise BrokerAPIError()
        return settlement_id
