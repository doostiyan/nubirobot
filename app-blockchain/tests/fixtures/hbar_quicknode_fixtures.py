import pytest

@pytest.fixture
def tx_details_successful_transaction():
    return '0.0.1070126-1662368439-606540089'

@pytest.fixture
def tx_details_invalid_transaction():
    return '0.0.14622-1662367091-224352244'

@pytest.fixture
def tx_details_fail_transaction():
    return '0.0.911748-1661769086-456664222'

@pytest.fixture
def account_address():
    return '0.0.1686716'