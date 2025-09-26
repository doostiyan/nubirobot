import pytest


@pytest.fixture
def tx_hash_successful():
    return '1644169A20EFB2109F8F24A992DD2151DF89F0BE1757ACE89CBA7E1DA9219C7D'

@pytest.fixture
def tx_hash_failed():
    return '5C183F671DE0BD3F46E905D4478141D49BABDB4DE347E293E3518CC0FC86BF74'

@pytest.fixture
def addresses():
    return ['dydx10sdnqxvrwe3mhducn6plyewul84edgd47rfnfe']
