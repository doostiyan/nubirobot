from decimal import Decimal

import pytest

from exchange.base.formatting import get_decimal_places


@pytest.mark.unit
def test_normalize_digits():
    assert get_decimal_places(Decimal('0.10000')) == 1
    assert get_decimal_places(Decimal('1E+7')) == 0
    assert get_decimal_places(Decimal('1E-7')) == 7
    assert get_decimal_places(Decimal('0.10001')) == 5
