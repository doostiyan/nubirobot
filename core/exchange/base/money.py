import math
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN


def money_is_close(a, b):
    """ An improved version of math.isclose for comparing crypto values
    """
    if isinstance(a, (int, float)):
        a = Decimal(a)
    if isinstance(b, (int, float)):
        b = Decimal(b)
    return (a - b).copy_abs() < Decimal('1E-8')


def money_is_close_decimal(a, b, decimals=8):
    """ An improved version of math.isclose for comparing crypto values
    """
    if a is None or b is None:
        return False
    if isinstance(a, (int, float)):
        a = Decimal(a)
    if isinstance(b, (int, float)):
        b = Decimal(b)
    return (a - b).copy_abs() < Decimal(f'1E-{decimals}')


def money_is_zero(a):
    """ Checks if the given number is reasonably a zero value
    """
    zero = Decimal('0')
    if a < zero:
        # Monetary values should be always non-zero, so we
        #  treat negative values as close to zero
        return True
    return money_is_close(a, zero)


def normalize(x, exp, **kwargs):
    """Return a normalized representation of x quantized to exp,
    but always return a non-exponential representation.

    * if exp parameter is None, no quantization is performed.
    * Source: https://docs.python.org/3/library/decimal.html#decimal-faq
    """
    if isinstance(x, (int, float)):
        x = Decimal(x)
    if exp is not None:
        x = x.quantize(exp, **kwargs)
    if x == x.to_integral():
        return x.quantize(Decimal('1'))
    return x.normalize()


def humanize_number(x, precision=None, multiplier=None):
    """ Makes the given number to have a reasonable precision
          e.g. $1000.01 can usually become $1000 without financial impact

        x: The number to humanize. Can be amount/price/count/etc. of something.
        precision: The minimum precision defined for x
        multiplier: Used when there is an intrinsic value in x, e.g. when
          it is represent a share of something valuable. This will handle
          cases when the value is so large that even small fractions should
          be conserved.
    """
    if isinstance(x, int) or isinstance(x, float):
        x = Decimal(x)
    # Determine natural precision
    trivial = Decimal('0')
    y = x * (multiplier or Decimal('1'))
    if y >= Decimal('100_000'):
        trivial = Decimal('100')
    elif y >= Decimal('10_000'):
        trivial = Decimal('10')
    elif y >= Decimal('1_000'):
        trivial = Decimal('1')
    elif y >= Decimal('100'):
        trivial = Decimal('0.1')
    elif y >= Decimal('10'):
        trivial = Decimal('0.01')
    elif y >= Decimal('1'):
        trivial = Decimal('0.001')
    elif y >= Decimal('0.1'):
        trivial = Decimal('0.0001')
    else:
        trivial = Decimal('0.00001')
    # Considering parameters
    if multiplier:
        trivial /= multiplier
    if precision and precision > trivial:
        trivial = precision
    # Do the rounding
    if trivial > Decimal('1'):
        rem = x % trivial
        x -= rem
        if 2 * rem > trivial:
            x += trivial
    else:
        x = x.quantize(trivial)
    return x


def quantize_number(number, precision=Decimal('10'), rounding=ROUND_HALF_UP):
    if precision >= Decimal('1'):
        number /= precision
        number = number.to_integral_value(rounding)
        number *= precision
    else:
        number = number.quantize(precision, rounding)
    return number


def format_small_money(value: Decimal, **_) -> str:
    """This method could be used in cases when there is the need for rounding a very small monetary value
    (for example users margin pool interests) which our conventional formatters would result zero.
    """
    if value <= 0:
        raise ValueError('A Monetary Value Should be Positive')
    most_valuable_non_whole_digit_power = min(0, math.floor(math.log10(value)))
    quantized_value = value.quantize(Decimal(f'1E{most_valuable_non_whole_digit_power-2}'), rounding=ROUND_DOWN)
    return f'{quantized_value.normalize():.10f}'.rstrip('0').rstrip('.')
