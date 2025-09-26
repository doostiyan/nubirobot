import binascii
import os
from decimal import Decimal

from django.conf import settings

from exchange.base.models import Currencies
from exchange.base.serializers import serialize_choices


def get_toman_amount_display(amount: Decimal) -> int:
    if amount < 3 * 10e4:
        return 1
    if amount < 5 * 10e4:
        return 2
    elif amount < 10e5:
        return 3
    elif amount < 5 * 10e5:
        return 4
    elif amount < 10e6:
        return 5
    elif amount < 25 * 10e5:
        return 6
    elif amount < 50 * 10e5:
        return 7
    elif amount < 10e7:
        return 8
    elif amount < 2 * 10e7:
        return 9
    elif amount < 5 * 10e7:
        return 10
    return 11


def get_tether_amount_display(amount: Decimal) -> int:
    if amount < 11:
        return 1
    if amount < 15:
        return 2
    elif amount < 20:
        return 3
    elif amount < 50:
        return 4
    elif amount < 100:
        return 5
    elif amount < 200:
        return 6
    elif amount < 500:
        return 7
    elif amount < 1000:
        return 8
    elif amount < 2000:
        return 9
    elif amount < 5000:
        return 10
    elif amount < 10000:
        return 11
    return 12


def get_amount_display(amount: Decimal, currency: int) -> int:
    """
    **Warning:** This function currently only supports USDT and RIAL Currencies.
    """
    if currency == Currencies.usdt:
        return get_tether_amount_display(amount)
    return get_toman_amount_display(amount)


def is_webengage_user(user: "User") -> bool:
    from exchange.accounts.models import User

    if user.id in settings.TRUSTED_USER_IDS or user.id <= 1000 or user.user_type >= User.USER_TYPES.trusted :
        return False
    return True


def generate_key():
    return binascii.hexlify(os.urandom(30)).decode()


def convert_order_channel_to_kind_device(channel: int):
    from exchange.market.models import Order

    if channel >= Order.CHANNEL.api and channel < Order.CHANNEL.web_v1:
        return 'b'
    if channel >= Order.CHANNEL.web_v1 and channel < Order.CHANNEL.system_margin:
        return None
    if channel >= Order.CHANNEL.system_margin and channel < Order.CHANNEL.locket:
        return 's'
    if channel > Order.CHANNEL.locket:
        return None

    channel_name = serialize_choices(Order.CHANNEL, channel)
    return channel_name[0] if channel_name else None
