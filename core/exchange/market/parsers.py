from exchange.base.models import VALID_MARKET_SYMBOLS
from exchange.base.parsers import parse_choices
from exchange.base.api import NobitexAPIError, ParseError
from .models import Market, Order


def parse_order_mode(s):
    if not s:
        return 'default'
    s = str(s).lower()
    if s not in ('oco', 'default'):
        raise ParseError('Invalid mode')
    return s


def parse_order_type(s, **kwargs):
    return parse_choices(Order.ORDER_TYPES, s, **kwargs)


def parse_order_status(s, **kwargs):
    return parse_choices(Order.STATUS, s, **kwargs)


def parse_order_execution(s, **kwargs):
    return parse_choices(Order.EXECUTION_TYPES, s, **kwargs)


def parse_order_trade_type(s, **kwargs):
    return parse_choices(Order.TRADE_TYPES, s, **kwargs)


def parse_symbol(s, **kwargs):
    symbol = (s or '').upper()
    if symbol not in VALID_MARKET_SYMBOLS:
        raise NobitexAPIError('InvalidSymbol', 'The symbol "{}" is not a valid market pair.'.format(symbol))
    return symbol


def parse_market(s, **kwargs):
    symbol = parse_symbol(s)
    return Market.by_symbol(symbol)
