import datetime
import math
import re
from decimal import Decimal, InvalidOperation
from enum import Enum
from string import ascii_letters, digits
from typing import Dict, Optional, Type, TypedDict, TypeVar
from uuid import UUID

import pytz
from model_utils import Choices

from exchange.base.constants import ZERO

from .api import ParseError
from .calendar import ir_tz
from .models import Currencies, Exchange


def parse_int(s, required=False, minimum: int = None, **_):
    if not s:
        if required:
            raise ParseError('Missing integer value')
        return None
    s = str(s)
    try:
        s = int(s)
    except ValueError:
        raise ParseError('Invalid integer value: "{}"'.format(s))
    if minimum is not None and s < minimum:
        raise ParseError(f'Value must be greater than or equal to {minimum}')
    return s


def parse_float(s, required=False, **_):
    if s is None or s == '':
        if required:
            raise ParseError('Missing float value')
        return None
    s = str(s)
    try:
        return float(s)
    except ValueError:
        raise ParseError('Invalid float value: "{}"'.format(s))


def parse_str(s, required=False, max_length=1000, **_):
    s = str(s or '')[:max_length].strip()
    if not s and required:
        raise ParseError('Missing string value')
    return s


def parse_bool(s, required=False, **_):
    if s is None or s == '':
        if required:
            raise ParseError('Missing boolean value')
        return None
    if isinstance(s, bool):
        return s
    if isinstance(s, str):
        s = s.lower()
        if s in ['yes', 'on', 'true']:
            return True
        if s in ['no', 'off', 'false']:
            return False
    raise ParseError('Invalid boolean value: "{}"'.format(s))


def parse_iso_date(s, required=False, **_):
    if not s:
        if required:
            raise ParseError('Missing datetime value')
        return None
    if s.endswith('+00:00'):
        s = s[:-6] + 'Z'
    has_microsecond = '.' in s
    if has_microsecond:
        fmt = '%Y-%m-%dT%H:%M:%S.%fZ'
        s = re.sub(r'\.(\d{,6})(\d*)Z', r'.\g<1>Z', s)
    else:
        fmt = '%Y-%m-%dT%H:%M:%SZ'
    return pytz.utc.localize(datetime.datetime.strptime(s, fmt))


def parse_date(s, required=False, **_):
    if not s:
        if required:
            raise ParseError('Missing date value')
        return None
    fmt = '%Y-%m-%d'
    irtz = pytz.timezone('Asia/Tehran')
    try:
        date = datetime.datetime.strptime(s, fmt)
    except ValueError:
        raise ParseError('Invalid date format')
    return irtz.localize(date)


def parse_timestamp(s, required=False, **_):
    if not s:
        if required:
            raise ParseError('Missing datetime value')
        return None
    return pytz.utc.localize(datetime.datetime.fromtimestamp(s))


def parse_utc_timestamp(s, required=False, **_):
    if not s:
        if required:
            raise ParseError('Missing datetime value')
        return None
    return datetime.datetime(1970, 1, 1, 0, 0, 0, 0, pytz.utc) + datetime.timedelta(seconds=parse_int(s))


def parse_utc_timestamp_from_2000(s, required=False, **_):
    if not s:
        if required:
            raise ParseError('Missing datetime value')
        return None
    return datetime.datetime(2000, 1, 1, 0, 0, 0, 0, pytz.utc) + datetime.timedelta(seconds=parse_int(s))


def parse_utc_timestamp_ms(s, required=False, **_):
    if not s:
        if required:
            raise ParseError('Missing datetime value')
        return None
    s = parse_int(s)
    return parse_utc_timestamp(s // 1000) + datetime.timedelta(microseconds=(s % 1000) * 1000)


def parse_choices(choices, s, required=False, **_):
    class_name = choices.__class__.__name__.lower()
    if not s:
        if required:
            raise ParseError('Missing {} value'.format(class_name))
        return None
    s = str(s)
    try:
        return getattr(choices, s)
    except AttributeError:
        raise ParseError('Invalid {}: "{}"'.format(class_name, s))


def parse_currency(s, **kwargs):
    return parse_choices(Currencies, s, **kwargs)


def parse_money(s, required=False, allow_zero=False, field=None, **_):
    from .helpers import get_max_db_value
    if not s:
        if s is not None and allow_zero:
            return ZERO
        if required:
            raise ParseError('Missing monetary value')
        return None
    s = str(s)
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ParseError('Invalid monetary value: "{}"'.format(s))
    if not math.isfinite(d):
        raise ParseError('Invalid numeric value: "{}"'.format(s))
    if d < 0 or not allow_zero and d == 0:
        raise ParseError('Only positive values are allowed for monetary values.')
    if field:
        max_allowed_value = get_max_db_value(field)
        if d > max_allowed_value:
            raise ParseError(f'Numeric value out of bound: "{s}"')
    return d


def parse_decimal(s, required=False, allow_zero=False, **_):
    if not s:
        if s is not None and allow_zero:
            return ZERO
        if required:
            raise ParseError('Missing numeric value')
        return None
    try:
        return Decimal(str(s))
    except InvalidOperation:
        raise ParseError(f'Invalid numeric value: "{s}"')


def parse_strict_decimal(s, exp: Decimal, required=False, **_):
    d = parse_decimal(s, required=required, allow_zero=True)
    if d is None and not required:
        return d

    if d != d.quantize(exp):
        raise ParseError(f'numeric value should have precision of {exp}')

    return d


def parse_uuid(s, required=False, **_):
    if not s:
        if required:
            raise ParseError('Missing uuid value')
        return None
    s = str(s)
    try:
        val = UUID(s, version=4)
    except ValueError:
        raise ParseError('Invalid monetary value: "{}"'.format(s))

    return val


def parse_tag(s, is_integer, required=False):
    if not s:
        if required:
            raise ParseError('Missing uuid value')
        return None
    if is_integer:
        tag = parse_int(s)
        # Tag is unsigned 32 bit int
        tag = tag % 2 ** 32
        return tag
    return str(s)


def parse_utc_timestamp_nanosecond(s, required=False, **_):
    if not s:
        if required:
            raise ParseError('Missing datetime value')
        return None
    s = parse_int(s)
    return datetime.datetime.utcfromtimestamp(s / 1e9)


def parse_exchange(s: str) -> int:
    for exchange, exchange_name in Exchange.CHOICES:
        if s == exchange_name:
            return exchange
    raise ParseError(f'Invalid Exchange name "{s}"')


def parse_client_order_id(s: str, required=False) -> str:
    if not s:
        if required:
            raise ParseError('Missing clientOrderId')
        return s

    if not isinstance(s, str):
        raise ParseError('clientOrderId should be string')

    if len(s) > 32:
        raise ParseError(f'Invalid clientOrderId "{s}"')

    if not all(c in ascii_letters + digits + '-' for c in s):
        raise ParseError(f'Invalid clientOrderId "{s}"')

    return s


def parse_timestamp_microseconds(s, required=False, **_):
    has_microsecond = False
    if not s:
        if required:
            raise ParseError('Missing datetime value')
        return None
    s = parse_int(s)
    if len(str(s)) > 10:
        has_microsecond = True
    if has_microsecond:
        return parse_utc_timestamp(s // 1000000) + datetime.timedelta(microseconds=(s % 1000000))
    else:
        return parse_utc_timestamp(s)


def parse_item_list(s, item_type: type, required: bool = False) -> list:
    if not s:
        if required:
            raise ParseError('Missing list value')
        return []
    if not isinstance(s, list):
        raise ParseError(f'Invalid list "{s}"')
    for item in s:
        if not isinstance(item, item_type):
            raise ParseError(f'Invalid list item type "{type(s)}" for "{s}"')
    return s


def parse_utc_timestamp_to_ir_time(utc_ts: str, required: bool = False) -> Optional[datetime.datetime]:
    if not utc_ts:
        if required:
            raise ParseError('Missing datetime value')
        return None
    utc_ts = parse_float(utc_ts)
    return datetime.datetime.fromtimestamp(utc_ts, tz=ir_tz())


def parse_multi_choices(choices, l, max_len=5, required=False):
    if not l:
        if required:
            raise ParseError('Missing multi choices value')
        return None

    if not isinstance(l, str):
        try:
            l = str(l)
        except TypeError as ex:
            raise ParseError('Invalid multi choices type') from ex

    items = l.strip().strip(', ').split(',')
    if len(items) > max_len:
        raise ParseError(f'Multi choices is too long, max len is {max_len}')

    results = []
    for item in items:
        result = parse_choices(choices, item, required=True)
        results.append(result)

    return results


class WalletBulkTransferData(TypedDict):
    src_type: int
    dst_type: int
    transfers: Dict[int, Decimal]


def parse_bulk_wallet_transfer(
    bulk_transfer_dto,
    max_len: int,
    wallet_choices: Choices,
    *,
    required: bool = False,
) -> Optional[WalletBulkTransferData]:
    if not bulk_transfer_dto:
        if required:
            raise ParseError('Missing wallet transfers value')
        return None

    if not isinstance(bulk_transfer_dto, dict):
        raise ParseError(f'Input should be a dict: "{bulk_transfer_dto}"')

    transfers = bulk_transfer_dto.get('transfers')
    if transfers is None:
        raise ParseError('transfers is missing')

    if not isinstance(transfers, list):
        raise ParseError('transfers must be a list')

    if len(transfers) == 0:
        raise ParseError('transfers is empty')

    if len(transfers) > max_len:
        raise ParseError(f'List is too long, max len is {max_len}')

    result: WalletBulkTransferData = {
        'src_type': parse_choices(wallet_choices, bulk_transfer_dto.get('srcType'), required=True),
        'dst_type': parse_choices(wallet_choices, bulk_transfer_dto.get('dstType'), required=True),
        'transfers': {},
    }
    for item in transfers:
        currency = parse_currency(item.get('currency'), required=True)
        amount = parse_money(item.get('amount'), required=True)
        result['transfers'][currency] = amount

    return result


def parse_word(s, *, required: bool = False):
    s = str(s or '').strip()
    if not s and required:
        raise ParseError('Missing word value')
    if not s and not required:
        return ''
    if not re.match(r'^[a-zA-Z0-9\-]+$', s):
        raise ParseError('Invalid word, it should only contain chars, digits and hyphen')
    return s


_E = TypeVar('_E', bound=Enum)


def parse_enum(e: Type[_E], s: str, *, required: bool = False) -> Optional[_E]:
    s = str(s or '').strip()
    if not s:
        if required:
            raise ParseError('Missing enum value')
        return None

    v = getattr(e, s, None)
    if v is None:
        raise ParseError(f'Invalid enum: "{s}"')
    return v


def parse_limited_length_string(s: str, max_length: int) -> str:
    if s is None:
        raise ParseError('Empty string')
    if len(s) > max_length:
        raise ParseError(f'Too long string, max length is {max_length}')
    return s
