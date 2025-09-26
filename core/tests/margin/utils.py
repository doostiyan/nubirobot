from decimal import Decimal


def get_trade_fee_mock(market, user=None, amount=None, is_maker=False, is_buy=False):
    fee_rate = Decimal('0.1') if is_maker else Decimal('0.15')
    return fee_rate * amount / 100


def get_user_fee_by_fields_mock(amount=None, is_maker=False, **_):
    fee_rate = Decimal('0.1') if is_maker else Decimal('0.15')
    return fee_rate * amount / 100
