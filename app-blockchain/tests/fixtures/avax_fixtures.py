import pytest


@pytest.fixture
def tx_hash_successful():
    return '0x0525e4e83b437ca4bc1b1eab779a189478ef656786ce6f35e770969db3491dd2'


@pytest.fixture
def tx_hash_failed():
    return '0xa3a10a698f40644a674deeefef241e601bd135ad42a6d245b3e6501942a65fd5'


@pytest.fixture
def wallet():
    return '0x7f97a2de263EdA97Db2ed4FAC8fFf27f5883d8f1'

@pytest.fixture
def block_number():
    return 63337297
