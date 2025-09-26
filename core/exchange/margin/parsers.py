from decimal import Decimal

from django.conf import settings

from exchange.base.api import ParseError
from exchange.base.parsers import parse_choices, parse_decimal, parse_int
from exchange.margin.models import Position


def parse_extension_days(s) -> int:
    extension_days = parse_int(s) or 0
    if not 0 <= extension_days <= settings.POSITION_EXTENSION_LIMIT:
        raise ParseError(f'Extension days must be a number between 0 and {settings.POSITION_EXTENSION_LIMIT}')
    return extension_days


def parse_pnl_percent(s, **kwargs) -> int:
    pnl_percent = parse_int(s, **kwargs) or 0
    if abs(pnl_percent) > 100:
        raise ParseError('PNL percent is out of range')
    return pnl_percent


def parse_leverage(s) -> Decimal:
    s = parse_decimal(s)
    if s is None:
        return Position.BASE_LEVERAGE
    if s < 1 or s % Decimal('0.5'):
        raise ParseError(f'Invalid leverage {s}')
    return s


def parse_position_side(s, **kwargs) -> int:
    return parse_choices(Position.SIDES, s, **kwargs)
