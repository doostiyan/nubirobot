import datetime
from decimal import Decimal
from typing import Optional

from exchange.web_engage.events.base import WebEngageKnownUserEvent
from exchange.web_engage.utils import get_toman_amount_display


class DepositWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "deposit"

    def __init__(self, user, currency: int, amount: Decimal, tp: str, event_time: Optional[datetime.datetime] = None):
        super().__init__(user, event_time)
        self.currency = currency
        self.amount = amount
        self.tp = tp

    def _get_data(self) -> dict:
        from exchange.wallet.estimator import PriceEstimator
        rial_value = PriceEstimator.get_rial_value_by_best_price(self.amount, self.currency, 'sell')
        return {
            "currency": self.currency,
            "user_level_code": self.user.user_type,
            "amount_code": get_toman_amount_display(amount=rial_value),
            "type": self.tp,
        }


class WithdrawWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "withdraw"

    def __init__(self, user, currency: int, amount: Decimal, event_time: Optional[datetime.datetime] = None):
        super().__init__(user, event_time)
        self.currency = currency
        self.amount = amount

    def _get_data(self) -> dict:
        from exchange.wallet.estimator import PriceEstimator
        rial_value = PriceEstimator.get_rial_value_by_best_price(self.amount, self.currency, 'sell')
        return {"currency": self.currency,
                "user_level_code": self.user.user_type,
                "amount_code": get_toman_amount_display(amount=rial_value)}


class ShetabGatewayUnavailableWebEngageEvent(WebEngageKnownUserEvent):
    event_name = 'shetab_gateway_unavailable'

    def _get_data(self) -> dict:
        return {}
