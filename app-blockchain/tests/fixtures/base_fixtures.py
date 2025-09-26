import pytest


@pytest.fixture
def tx_hash_successful():
    return '0x772283cd67385987a0a7bb7efe1679b4e3b56deabd4945d874ed8777b25873fc'


@pytest.fixture
def token_tx_hash_successful():
    return '0x5bb7565009f0d12dd059640e30cf7de7f281f2997505655b0568d398a4c6bba9'


@pytest.fixture
def tx_hash_failed():
    return '0xa3a10a698f40644a674deeefef241e601bd135ad42a6d245b3e6501942a65fd5'


@pytest.fixture
def wallet():
    return '0x2B3a42071674B13bc4020aDda4567cDb5AB284A5'

@pytest.fixture
def block_number():
    return 30088058
