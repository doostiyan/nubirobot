import datetime
from decimal import Decimal
from typing import Optional

from exchange.web_engage.events.base import WebEngageKnownUserEvent
from exchange.web_engage.utils import get_amount_display


class MarginTransactionEngageEvent(WebEngageKnownUserEvent):
    event_name = 'margin_transaction'

    def __init__(self, user, currency: int, amount: Decimal, event_time: Optional[datetime.datetime] = None):
        """
        Warning: This event currently only supports USDT and BTC wallets and operates in Safe mode.
        """
        super().__init__(user, event_time)
        self.currency = currency
        self.amount = amount

    def _get_data(self) -> dict:
        amount = abs(self.amount)
        sign = -1 if self.amount < 0 else 1
        return {
            'currency': self.currency,
            'user_level_code': self.user.user_type,
            'amount_code': get_amount_display(amount=amount, currency=self.currency) * sign,
        }
