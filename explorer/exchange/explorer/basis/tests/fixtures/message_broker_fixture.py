import pytest
from unittest.mock import Mock

@pytest.fixture
def message_broker():
    return Mock() 