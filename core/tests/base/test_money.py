from decimal import Decimal

import pytest

from exchange.base.models import AMOUNT_PRECISIONS, PRICE_PRECISIONS
from exchange.base.money import format_small_money, humanize_number, money_is_close, money_is_zero, normalize


@pytest.mark.unit
def test_money_is_close():
    assert money_is_close(Decimal('1e-9'), Decimal('0'))
    assert money_is_close(Decimal('1e-32'), Decimal('0'))
    assert not money_is_close(Decimal('0.0001'), Decimal('0'))
    assert money_is_close(Decimal('0.000000000001'), Decimal('0'))
    assert money_is_close(Decimal('0.999999999'), Decimal('1'))
    assert money_is_close(Decimal('100.000000001'), Decimal('100'))
    assert not money_is_close(Decimal('1000.00001'), Decimal('100'))
    assert money_is_close(1, 1)
    assert money_is_close(0.1 + 0.2, 0.3)


@pytest.mark.unit
def test_money_is_zero():
    assert money_is_zero(Decimal('0'))
    assert money_is_zero(Decimal('1e-9'))
    assert money_is_zero(Decimal('1e-20'))
    assert not money_is_zero(Decimal('0.00001'))
    assert not money_is_zero(Decimal('1.0000000000001'))
    assert money_is_zero(Decimal('-1'))
    assert money_is_zero(0)
    assert money_is_zero(0.1 + 0.2 - 0.3)


@pytest.mark.unit
def test_normalize():
    assert str(normalize(Decimal('0.001532'), Decimal('1e-5'))) == '0.00153'
    assert str(normalize(Decimal('0.010002'), Decimal('1e-3'))) == '0.01'
    assert str(normalize(Decimal('1871232000'), Decimal('10'))) == '1871232000'
    assert str(normalize(Decimal('0.04975193'), Decimal('1e-6'))) == '0.049752'
    assert str(normalize(Decimal('0.04975193'), Decimal('1e-1'))) == '0'
    assert str(normalize(Decimal('0.123'), Decimal('1e-1'))) == '0.1'
    assert str(normalize(Decimal('0.04975193'), Decimal('1e-2'))) == '0.05'
    assert str(normalize(Decimal('12.1'), exp=Decimal('1'))) == '12'
    assert str(normalize(Decimal('273000'), exp=None)) == '273000'


@pytest.mark.unit
def test_humanize_number():
    # Sample IRT market prices
    assert humanize_number(Decimal('103_015_123_0'), multiplier=Decimal('.1')) == Decimal('103_015_100_0')
    assert humanize_number(Decimal('1_978_703_0'), multiplier=Decimal('.1')) == Decimal('1_978_700_0')
    assert humanize_number(Decimal('599_590_0'), multiplier=Decimal('.1')) == Decimal('599_600_0')
    assert humanize_number(Decimal('201_490_0'), multiplier=Decimal('.1')) == Decimal('201_500_0')
    assert humanize_number(Decimal('13_751_0'), multiplier=Decimal('.1')) == Decimal('13_750_0')
    assert humanize_number(Decimal('13_751_0'), multiplier=Decimal('.1')) == Decimal('13_750_0')
    assert humanize_number(Decimal('2_963_1'), multiplier=Decimal('.1')) == Decimal('2_963_0')
    # Sample USDT market prices
    assert humanize_number(Decimal('7221.02')) == Decimal('7221')
    assert humanize_number(Decimal('144.89')) == Decimal('144.9')
    assert humanize_number(Decimal('43.78')) == Decimal('43.78')
    assert humanize_number(Decimal('14.999')) == Decimal('15.00')
    assert humanize_number(Decimal('2.5923')) == Decimal('2.592')
    assert humanize_number(Decimal('5.11191')) == Decimal('5.112')
    assert humanize_number(Decimal('0.21986')) == Decimal('0.2199')
    assert humanize_number(Decimal('0.05304')) == Decimal('0.05304')
    # Precision parameter
    assert humanize_number(Decimal('14.9784066'), precision=Decimal('1e-4')) == Decimal('14.98')


@pytest.mark.unit
def test_format_small_money():
    assert format_small_money(Decimal('1.0')) == '1'
    assert format_small_money(Decimal('1.10')) == '1.1'
    assert format_small_money(Decimal('1.1111')) == '1.11'
    assert format_small_money(Decimal('.01127')) == '0.0112'
    assert format_small_money(Decimal('.004567')) == '0.00456'
    assert format_small_money(Decimal('.00011122')) == '0.000111'
    assert format_small_money(Decimal('0.11122E-3')) == '0.000111'
    assert format_small_money(Decimal('11.122E-5')) == '0.000111'
    assert format_small_money(Decimal('0.011122E-2')) == '0.000111'


@pytest.mark.unit
def test_precisions():
    assert set(AMOUNT_PRECISIONS) == set(PRICE_PRECISIONS)
