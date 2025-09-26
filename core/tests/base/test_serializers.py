import pytest
from decimal import Decimal

from model_utils import Choices

from exchange.base.serializers import serialize_decimal, serialize_choices


@pytest.mark.unit
def test_serialize_decimal():
    assert serialize_decimal(Decimal('12.3')) == '12.3'
    assert serialize_decimal(Decimal('-100.00')) == '-100'
    assert serialize_decimal(Decimal('99.999')) == '99.999'
    assert serialize_decimal(Decimal('1926053.39087248712')) == '1926053.39087248712'
    assert serialize_decimal(Decimal('1523669722187.85817034714')) == '1523669722187.85817034714'
    assert serialize_decimal(Decimal('1523669722187.000000000001')) == '1523669722187.000000000001'
    assert serialize_decimal(Decimal('1_668_013_131_2')) == '16680131312'
    assert serialize_decimal(Decimal('0.0000000019')) == '0.0000000019'
    assert serialize_decimal(Decimal('-0.00003')) == '-0.00003'
    assert serialize_decimal(Decimal('10000000')) == '10000000'
    assert serialize_decimal(Decimal('0E+0')) == '0'
    assert serialize_decimal(Decimal('1e7')) == '10000000'
    assert serialize_decimal(Decimal('0E-10')) == '0'
    assert serialize_decimal(Decimal('274450.0000000000')) == '274450'
    assert serialize_decimal(Decimal('1.23E5')) == '123000'
    assert serialize_decimal(Decimal('6.780E-7')) == '0.000000678'


@pytest.mark.unit
def test_serialize_choices():
    SAMPLE_CHOICES = Choices(
        (1, 'red', 'قرمز'),
        (2, 'yellow', 'زرد'),
        (3, 'green', 'سبز'),
    )
    assert SAMPLE_CHOICES.red == 1
    assert serialize_choices(SAMPLE_CHOICES, 1) == 'red'
    assert SAMPLE_CHOICES.yellow == 2
    assert serialize_choices(SAMPLE_CHOICES, 2) == 'yellow'
    assert SAMPLE_CHOICES.green == 3
    assert serialize_choices(SAMPLE_CHOICES, 3) == 'green'
