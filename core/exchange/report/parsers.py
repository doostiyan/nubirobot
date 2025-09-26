from exchange.base.parsers import parse_choices, ParseError, parse_int
from exchange.report.models import DailyShetabDeposit, DailyWithdraw, DailyJibitDeposit


def parse_daily_shetab_deposit_status(s, **kwargs):
    return parse_choices(DailyShetabDeposit.STATUS, s.lower(), **kwargs)


def parse_daily_bank_deposit_status(s, **kwargs):
    if s.lower() == 'success':
        s = 'SUCCESSFUL'
    if s.lower() == 'waiting_verify':
        s = 'WAITING_FOR_MERCHANT_VERIFY'
    return parse_choices(DailyJibitDeposit.STATUS, s.lower(), **kwargs)


def parse_daily_withdraw_status(s, **kwargs):
    return parse_choices(DailyWithdraw.STATUS, s.lower(), **kwargs)


def parse_jibit_reference_number(s):
    if not isinstance(s, str):
        raise ParseError(f'Invalid str value: "{s}"')
    if not s.startswith('nobitex'):
        raise ParseError(f'Invalid reference number format: "{s}"')
    pk = s.replace('nobitex', '', 1)
    return parse_int(pk, required=True)
