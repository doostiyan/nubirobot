import pytest


@pytest.fixture(scope="session")
def app():
    from nobitex.api.apifast import app
    return app