from exchange.base.api import ParseError
from exchange.base.parsers import parse_choices
from exchange.pricealert.models import PriceAlert


def parse_direction(s, required=False, **_):
    if s == '+':
        return True
    if s == '-':
        return False
    if required:
        raise ParseError('Missing direction value')
    return None


def parse_channel(s, **kwargs):
    if not s:
        return None
    return sum(parse_choices(PriceAlert.CHANNELS, channel, **kwargs) for channel in s.split(','))


def parse_delete_item(s):
    if not s:
        return None
    try:
        res = [int(x) for x in s.split(',')]
    except Exception as e:
        raise ParseError(e)
    return res


def parse_alert_type(s, **kwargs):
    if not s:
        return None
    return parse_choices(PriceAlert.TYPES, s, **kwargs)
