import re
from http import HTTPStatus
from unittest.mock import patch

import fakeredis
import pytest
import responses

from exchange.asset_backed_credit.externals.base import NOBITEX_BASE_URL
from exchange.asset_backed_credit.externals.user import UserProfileSchema, VerificationProfileSchema
from exchange.asset_backed_credit.models.wallet import wallet_cache_manager
from exchange.base.models import Settings


@pytest.fixture(autouse=True)
def enable_abc_global_flags(request, db):
    Settings.set('abc_is_activated_apis', 'yes')
    Settings.set('abc_wallet_cache_read_enabled', 'yes')
    Settings.set('abc_wallet_cache_write_enabled', 'yes')


@pytest.fixture(autouse=True)
def global_mocks_responses():
    responses.start()
    add_global_mocks()
    yield responses
    responses.stop()
    responses.reset()


def add_global_mocks():
    url_pattern = re.compile(rf'^{re.escape(NOBITEX_BASE_URL)}/internal/users/([\w\-]+)/profile$')

    def request_callback(request):
        match = url_pattern.match(request.url)

        if match:
            uid = match.group(1)
            response_body = UserProfileSchema(
                uid=uid,
                username='username-' + str(uid),
                email=None,
                national_code=None,
                mobile=None,
                verification_status=0,
                user_type=1,
                verification_profile=VerificationProfileSchema(),
                gender=0,
                requires2fa=False,
                father_name='test',
                birthdate_shamsi='1390/12/12',
            )

            return HTTPStatus.OK, {'Content-Type': 'application/json'}, response_body.json(by_alias=True)
        return HTTPStatus.NOT_FOUND, {}, ''

    responses.add_callback(
        method=responses.GET,
        url=url_pattern,
        callback=request_callback,
        content_type='application/json',
    )


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis()


@pytest.fixture(autouse=True)
def wallet_cache_manager_get_client(redis_client):
    with patch.object(wallet_cache_manager, 'get_client', return_value=redis_client) as mock:
        yield mock
