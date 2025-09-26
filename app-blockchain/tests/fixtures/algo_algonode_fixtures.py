import pytest

@pytest.fixture
def tx_hash_successful():
    return 'TLFEB57OUCHHNUA6OUBPQHOANHJPLV3P533Z57XWOC26DHCXRGXA'

@pytest.fixture
def tx_hash_fail():
    return 'ELBKJQQF2FG4DMYCNZKQBO25UTQ2RF6BWUF33C365MHRJG4SFOHQ'

@pytest.fixture
def address():
    return 'QC7EZQEWHH4D7P4GG6EGIJIGG5E7ORURMMP5HFWUCN4ONT4LOQ7IVBCSNI'

@pytest.fixture
def from_block():
    return 31845478

@pytest.fixture
def to_block():
    return 31845490
