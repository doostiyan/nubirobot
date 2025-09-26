from datetime import datetime
from decimal import Decimal
from typing import Optional

from exchange.web_engage.events.base import WebEngageKnownUserEvent
from exchange.web_engage.utils import convert_order_channel_to_kind_device, get_amount_display


class OrderMatchedWebEngageEvent(WebEngageKnownUserEvent):
    event_name = 'order_matched'

    def __init__(
        self,
        user,
        src_currency: int,
        dst_currency: int,
        order_type: str,
        amount: Decimal,
        trade_type: str,
        leverage: Optional[int] = None,
        event_time: Optional[datetime] = None,
        channel: Optional[int] = None,
    ):
        super().__init__(
            user,
            event_time=event_time,
            device_kind=convert_order_channel_to_kind_device(channel) if channel else None,
        )
        self.source_currency = src_currency
        self.destination_currency = dst_currency
        self.order_type = order_type
        self.amount = amount
        self.trade_type = trade_type
        self.leverage = leverage or 1

    def _get_data(self) -> dict:
        return {
            'source_currency': str(self.source_currency),
            'destination_currency': str(self.destination_currency),
            'type': self.order_type,
            'user_level_code': self.user.user_type,
            'amount_code': get_amount_display(amount=self.amount, currency=self.destination_currency),
            'trade_type': self.trade_type,
            'leverage': str(self.leverage),
        }
