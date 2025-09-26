from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict

from dateutil import parser

from exchange.base.models import Currencies
from exchange.base.parsers import parse_choices
from exchange.liquidator.errors import BrokerAPIError4XX, InvalidAPIResponse, SettlementNotFound
from exchange.liquidator.models import Liquidation

from .base import BrokerBaseAPI


class SettlementStatusEnum(Enum):
    OPEN = 'open'
    FILLED = 'filled'
    PARTIALLY = 'partially'
    FAILED = 'failed'


@dataclass
class SettlementData:
    src_currency: str
    dst_currency: str
    side: str
    status: str
    amount: Decimal
    price: Decimal
    filled_amount: Decimal
    filled_price: Decimal
    issue_time: datetime
    expire_time: datetime
    server_time: datetime

    @staticmethod
    def _extract_datetime(data, key):
        try:
            data_timestamp = float(data.get(key))
        except ValueError:
            utc_datetime = parser.parse(data.get(key))
        else:
            utc_datetime = datetime.fromtimestamp(data_timestamp, tz=timezone.utc)

        return utc_datetime

    @classmethod
    def from_json(cls, data: Dict):
        return cls(
            src_currency=parse_choices(Currencies, data.get('baseCurrency').lower()),
            dst_currency=parse_choices(Currencies, data.get('quoteCurrency').lower()),
            side=parse_choices(Liquidation.SIDES, data.get('side').lower()),
            status=data.get('status'),
            amount=Decimal(data.get('amount', 0)),
            price=Decimal(data.get('price', 0)),
            filled_amount=Decimal(data.get('filledAmount', 0)),
            filled_price=Decimal(data.get('averageFillPrice', 0)),
            issue_time=cls._extract_datetime(data, 'createdAt'),
            expire_time=cls._extract_datetime(data, 'expiredAt'),
            server_time=cls._extract_datetime(data, 'serverTime'),
        )


class SettlementStatusErrorEnum(Enum):
    SETTLEMENT_NOT_FOUND = 'settlement not found'


class SettlementStatus(BrokerBaseAPI):
    url = '/liquidation/liquidation'
    method = 'get'
    metric_name = 'brokerSettlementStatus'

    def request(self, liquidation: Liquidation):
        try:
            response = self._request(params={'clientOrderId': liquidation.tracking_id})
        except BrokerAPIError4XX as e:
            message = str(e)
            if message == SettlementStatusErrorEnum.SETTLEMENT_NOT_FOUND.value:
                raise SettlementNotFound() from e
            raise

        try:
            settlement = SettlementData.from_json(response)
        except (TypeError, AttributeError) as e:
            raise InvalidAPIResponse() from e

        self._validate_settlement(settlement, liquidation)
        return settlement

    @staticmethod
    def _validate_settlement(settlement: SettlementData, liquidation: Liquidation):
        if (
            settlement.src_currency != liquidation.src_currency
            or settlement.dst_currency != liquidation.dst_currency
            or settlement.side != liquidation.side
            or settlement.amount != liquidation.amount
        ):
            raise InvalidAPIResponse()
