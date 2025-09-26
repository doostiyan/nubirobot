import pytest
from django.conf import settings
from pytest_mock import MockerFixture

from exchange.explorer.utils.test import NON_LOCALHOST_CLIENT, APIKeyMock


@pytest.fixture
def api_key_fixture(mocker: MockerFixture) -> str:
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch(
        'exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key',
        return_value=api_key
    )
    return api_key


@pytest.fixture
def auth_headers() -> dict:
    return {
        f'{settings.API_KEY_CUSTOM_HEADER.upper().replace("-", "_")}': 'key'
    }


@pytest.fixture
def non_localhost_ip() -> dict:
    return {'REMOTE_ADDR': NON_LOCALHOST_CLIENT}
