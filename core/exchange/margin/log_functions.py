from django.conf import settings
from django.utils import timezone

from exchange.accounts.models import Notification
from exchange.market.models import Order


def log_margin_order_cancel(margin_order: Order, inside_matcher: bool):
    is_system_margin = margin_order.channel == Order.CHANNEL.system_margin
    if not margin_order.is_margin:
        return

    source = 'inside matcher' if inside_matcher else 'outside matcher'
    if is_system_margin:
        system_margin_expiry_threshold = timezone.now() - settings.MARGIN_SYSTEM_ORDERS_MAX_AGE
        reason = (
            'Due to expiry time threshold'
            if margin_order.created_at < system_margin_expiry_threshold
            else 'Probably due to liquidity pool lack of enough credit'
        )
    elif inside_matcher:
        reason = 'liquidity pool lack of enough credit'
    else:
        return

    Notification.notify_admins(
        f'Position settlement order failed {source} with price: {margin_order.price}'
        f' matched:{margin_order.matched_amount} reason: {reason}',
        title=f'🧭 Margin - {margin_order.market_display}',
        channel='pool',
    )
