""" Xchange Parsers """

from exchange.base.parsers import parse_choices
from exchange.market.models import Order


def parse_order_type_is_sell(s, **kwargs):
    """ Return if the given order type is sell
    """
    kwargs['required'] = True
    return parse_choices(Order.ORDER_TYPES, s, **kwargs) == Order.ORDER_TYPES.sell
