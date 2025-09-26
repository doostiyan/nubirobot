import json
import re
from decimal import Decimal

from django.conf import settings

from exchange.base.models import Settings, get_currency_codename
from exchange.socialtrade.exceptions import (
    SubscriptionFeeIsLessThanTheMinimum,
    SubscriptionFeeIsMoreThanTheMaximum,
    SubscriptionIsNotAllowed,
)

FEE_BOUNDARY_KEY = 'social_trade_fee_boundary'


def validate_subscription_fee(subscription_currency: int, subscription_fee: Decimal):
    fee_boundary = Settings.get_json_object(FEE_BOUNDARY_KEY, json.dumps(settings.SOCIAL_TRADE['default_fee_boundary']))
    currency_codename = get_currency_codename(subscription_currency)
    if currency_codename not in fee_boundary['min'] or currency_codename not in fee_boundary['max']:
        raise SubscriptionIsNotAllowed()

    if subscription_fee < Decimal(fee_boundary['min'][currency_codename]):
        raise SubscriptionFeeIsLessThanTheMinimum()
    if subscription_fee > Decimal(fee_boundary['max'][currency_codename]):
        raise SubscriptionFeeIsMoreThanTheMaximum()


def is_nickname_valid(nickname: str) -> bool:
    max_length = settings.SOCIAL_TRADE['maxNicknameLength']
    min_length = settings.SOCIAL_TRADE['minNicknameLength']
    return bool(re.match(f'^[A-Za-z0-9]{{{min_length},{max_length}}}$', nickname))
