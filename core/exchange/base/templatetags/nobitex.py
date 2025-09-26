from django import template

from exchange.base.calendar import to_shamsi_date
from exchange.base.formatting import f_m, format_money, format_price, get_currency_unit
from exchange.base.models import CURRENCY_CODENAMES
from exchange.base.strings import _t

register = template.Library()


@register.filter
def moneyformat(value, arg):
    return f_m(value, c=arg)


@register.filter
def currencyformat(value, translate: bool = False):
    if translate:
        return _t(CURRENCY_CODENAMES.get(value))
    return get_currency_unit(value)


@register.filter
def moneycurrencyformat(value, arg):
    return format_money(value, currency=arg, show_currency=True)


@register.filter
def marketpriceformat(value, arg):
    return format_price(price=value, market_display=arg, show_currency=True)


@register.filter
def shamsidateformat(value):
    return to_shamsi_date(value)
