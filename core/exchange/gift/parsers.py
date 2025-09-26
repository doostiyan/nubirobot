from exchange.base.parsers import parse_choices

from exchange.gift.models import GiftCard


def parse_gift_type(s, **kwargs):
    return parse_choices(GiftCard.GIFT_TYPES, s, **kwargs)


def parse_gift_redeem(s, **kwargs):
    return parse_choices(GiftCard.REDEEM_TYPE, s, **kwargs)
