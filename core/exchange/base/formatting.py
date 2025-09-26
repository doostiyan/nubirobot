from decimal import Decimal
from typing import Optional

from exchange.base.strings import _t

from .models import AMOUNT_PRECISIONS, CURRENCY_CODENAMES, PRICE_PRECISIONS, Currencies, get_currency_codename


def f_m(m, c=None, show_c=False, en=False, exact=False, thousand_separators=True):
    """
    This method offers a better representation of numbers by some rounding, normalizing and redecorating them
    with separators.

    It can do the normalizing and rounding process according to the type of currency which had been passed to it
    via parameter "c". it also can show each number's currency type if the "show_c" is True.
    if "en" parameter has the value of "en" it shows 'RLS' and 'USD' currency types in abbreviated form, otherwise
    it shows them as their equivalent Persian acronym character.
    I assume the exact parameter was supposed to negate rounding effects, but never has been used.

    :param m: the number which passed.
    :param c: type of the currency(rls, usd, btc, usdt, xrp).
    :param show_c: indicates that the currency type should be shown with the number or not.
    :param en: 'en' or not 'en' that is the question.
    :param exact: never used.
    :param thousand_separators: you can choose to have thousand separators or not.
    :return: the "str" form of reformatted number given.
    """
    # Type Conversions
    if m is None:
        return None
    if not isinstance(m, Decimal):
        m = Decimal(m or 0)

    # How many decimal places to show
    places = {
        Currencies.rls: Decimal('1.'),
        Currencies.usd: Decimal('.01'),
        Currencies.btc: Decimal('.000001'),
        Currencies.usdt: Decimal('.01'),
        Currencies.xrp: Decimal('.00001'),
    }.get(c, Decimal('.001'))
    rep = str(m.quantize(places))

    # Adding thousand separators
    if thousand_separators:
        if '.' not in rep:
            rep += '.'
        rep_base, rep_decimal = rep.split('.')
        rep = ''
        for i, d in enumerate(rep_base):
            rep += d
            if (len(rep_base) - i) % 3 == 1:
                if i < len(rep_base) - 1:
                    rep += ','
        if rep_decimal:
            rep += '.' + rep_decimal

    # Adding unit to value
    if show_c:
        unit = get_currency_unit(c, en=en)
        if len(unit) == 1:
            rep = unit + rep
        else:
            rep = rep + ' ' + unit

    return rep


def format_money(
    money: Optional[Decimal],
    currency: Currencies,
    *,
    show_currency: bool = False,
    use_en: bool = False,
    thousand_separators: bool = True,
) -> Optional[str]:
    """
    Format a monetary amount as a string with optional currency symbol and thousand separators.

    Args:
        money (Optional[Decimal]): The monetary amount to format.
        currency (Currencies): The currency type.
        show_currency (bool, optional): Whether to include the currency symbol. Defaults to False.
        use_en (bool, optional): Whether to use English currency symbols. Defaults to False.
        thousand_separators (bool, optional): Whether to add thousand separators. Defaults to True.

    Returns:
        Optional[str]: The formatted monetary amount as a string or None if money is None.
    """

    # Type Conversions
    if money is None:
        return None

    if not isinstance(money, Decimal):
        money = Decimal(money or 0)

    # Convert Rial to Toman
    if currency == Currencies.rls:
        money /= 10

    # How many decimal places to show
    currency_codename = get_currency_codename(currency)
    places = AMOUNT_PRECISIONS.get(currency_codename.upper() + 'IRT', 1)

    # Add thousand separators
    if thousand_separators:
        formatted_money = f'{money.quantize(places).normalize():,f}'
    else:
        formatted_money = f'{money.quantize(places).normalize():f}'

    # Adding unit to value
    if show_currency:
        if use_en:
            unit = 'Toman' if currency == Currencies.rls else get_currency_unit(currency)
        else:
            unit = 'تومان' if currency == Currencies.rls else _t(CURRENCY_CODENAMES.get(currency))

        formatted_money = add_currency_unit(formatted_money, unit)

    return formatted_money


def format_price(
    price: Optional[Decimal],
    market_display: str,
    *,
    show_currency: bool = False,
    use_en: bool = False,
    thousand_separators: bool = True,
) -> Optional[str]:
    """
    Format a price as a string with optional dst currency symbol and thousand separators.

    Args:
        price (Optional[Decimal]): The price to format.
        market_display (str): Market symbol like BTC-USDT.
        show_currency (bool, optional): Whether to include the dst currency symbol. Defaults to False.
        use_en (bool, optional): Whether to use English currency symbols. Defaults to False.
        thousand_separators (bool, optional): Whether to add thousand separators. Defaults to True.

    Returns:
        Optional[str]: The formatted price as a string or None if price is None.
    """

    # Type Conversions
    if price is None:
        return None

    if not isinstance(price, Decimal):
        price = Decimal(price or 0)

    src, dst = market_display.split('-')
    dst = getattr(Currencies, dst.lower())
    # Convert Rial to Toman
    if dst == Currencies.rls:
        price /= 10

    # How many decimal places to show
    places = PRICE_PRECISIONS.get(market_display.replace('-', ''), 1)

    # Add thousand separators
    if thousand_separators:
        formatted_price = f'{price.quantize(places).normalize():,f}'
    else:
        formatted_price = f'{price.quantize(places).normalize():f}'

    # Adding unit to value
    if show_currency:
        if use_en:
            unit = 'Toman' if dst == Currencies.rls else get_currency_unit(dst)
        else:
            unit = 'تومان' if dst == Currencies.rls else _t(CURRENCY_CODENAMES.get(dst))

        formatted_price = add_currency_unit(formatted_price, unit)

    return formatted_price


def add_currency_unit(value: str, unit: str) -> str:
    """
    Add a currency unit to a monetary value string.

    Args:
        value (str): The monetary value string.
        unit (str): The currency unit.

    Returns:
        str: The monetary value string with the currency unit added.
    """
    return f'{value} {unit}' if len(unit) > 1 else f'{value}{unit}'


def get_currency_unit(currency, en=False):
    if currency == Currencies.rls:
        return 'RLS' if en else '﷼'
    if currency == Currencies.usd:
        return 'USD' if en else '$'
    return get_currency_codename(currency).upper()


def get_status_translation(status):
    return {
        'New': 'جدید',
        'Verified': 'تایید شده',
        'Accepted': 'پذیرفته شده',
        'Sent': 'ارسال شده',
        'Done': 'انجام شده',
        'Rejected': 'رد شده',
        'Processing': 'در حال پردازش',
        'Canceled': 'لغو شده',
        'Waiting': 'در انتظار',
    }.get(status, status)


def read_number(n, zpad=False):
    PERSIAN_NUMBERS_NAMES = [
        'صفر', 'یک', 'دو', 'سه', 'چهار', 'پنج', 'شش', 'هفت', 'هشت', 'نه',
        'ده', 'یازده', 'دوازده', 'سیزده', 'چهارده', 'پانزده', 'شانزده', 'هفده', 'هجده', 'نوزده']
    PERSIAN_NUMBERS_NAMES_10 = ['', 'ده', 'بیست', 'سی', 'چهل', 'پنجاه', 'شصت', 'هفتاد', 'هشتاد', 'نود', 'صد']
    PERSIAN_NUMBERS_NAMES_100 = ['', 'صد', 'دویست', 'سیصد', 'چهارصد', 'پانصد', 'ششصد', 'هفتصد', 'هشتصد', 'نهصد', 'هزار']

    if n is None:
        return ''
    try:
        n = int(n)
    except:
        return 'نامعتبر'
    if n < 0:
        return 'منفی ' + read_number(-n)
    if n < len(PERSIAN_NUMBERS_NAMES):
        prefix = ''
        if zpad and n < 10:
            prefix = 'صفر '
        return prefix + PERSIAN_NUMBERS_NAMES[n]
    if n < 100:
        s = PERSIAN_NUMBERS_NAMES_10[n // 10]
        m = n % 10
        if m > 0:
            s += ' و ' + PERSIAN_NUMBERS_NAMES[m]
        return s
    if n <= 1000:
        s = PERSIAN_NUMBERS_NAMES_100[n // 100]
        m = n % 100
        if m > 0:
            s += ' و ' + read_number(m)
        return s
    if n < 1E6:
        s = read_number(n // 1000) + ' هزار'
        m = n % 1000
        if m > 0:
            s += ' و ' + read_number(m)
        return s
    s = read_number(n // 1E6) + ' میلیون'
    m = n % 1E6
    if m > 0:
        s += ' و ' + read_number(m)
    return s


def get_decimal_places(amount: Decimal) -> int:
    # Normalize the amount to remove trailing zeros
    normalized_amount = amount.normalize()
    exponent = normalized_amount.as_tuple().exponent
    return max(-exponent, 0)

def convert_to_persian_digits(value:str)->str:
    persian_digits_map = {
        '0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴',
        '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹'
    }
    return ''.join(persian_digits_map.get(char, char) for char in value)
