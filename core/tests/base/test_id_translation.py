import pytest

from exchange.base.constants import MAX_32_INT, MIN_32_INT
from exchange.base.id_translation import decode_id, encode_id


@pytest.mark.parametrize(
    (
        'raw',
        'encoded',
    ),
    [
        (1, 1),
        (MAX_32_INT, MAX_32_INT),
        (0, MAX_32_INT - MIN_32_INT + 1),
        (-1, MAX_32_INT - MIN_32_INT),
        (-2, MAX_32_INT - MIN_32_INT - 1),
        (MIN_32_INT, MAX_32_INT + 1),
    ],
)
def test_id_translation(raw, encoded):
    assert encode_id(raw) == encoded
    assert decode_id(encoded) == raw
