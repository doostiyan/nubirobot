from exchange.accounts.models import Notification
from exchange.liquidator.models import Liquidation, LiquidationRequest


def check_double_spend_in_liquidation(liquidation: Liquidation):
    if round(abs(liquidation.amount / liquidation.filled_amount - 1), 2) != 0:
        Notification.notify_admins(
            f'Check liquidation data. liquidation: #{liquidation.pk}',
            title=f'‼️‼️‼️ Certain double spend in liquidation - {liquidation.symbol}',
            channel='liquidator',
        )


def check_double_spend_in_liquidation_request(liquidation_request: LiquidationRequest):
    if round(abs(liquidation_request.amount / liquidation_request.filled_amount - 1), 2) != 0:
        Notification.notify_admins(
            f'Check liquidation Request data. liquidation: #{liquidation_request.pk}',
            title=f'‼️‼️‼️ Certain double spend in liquidation Request - {liquidation_request.symbol}',
            channel='liquidator',
        )
