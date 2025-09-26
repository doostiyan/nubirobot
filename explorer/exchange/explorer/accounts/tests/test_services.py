from urllib.parse import urlencode

import pytest

from ...authentication.dtos import APIKeyDTO
from ...authentication.models import UserAPIKey
from ...utils.datetime import datetime2str
from ..dtos import UserDTO
from ..models import User
from ..services import get_user_dto


#
@pytest.mark.service
@pytest.mark.django_db
def test_get_user_dto_service():
    user = User.objects.create_user('test_user', 'test_email', 'test_password')
    test_api_key, _ = UserAPIKey.objects.create_key(name='test_api_key', user=user, rate='5/min')
    service_response = get_user_dto(user)
    transaction_details_dto = UserDTO(
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        date_joined=user.date_joined,
        api_keys=[
            APIKeyDTO(
                name=test_api_key.name,
                username=test_api_key.user.username,
                prefix=test_api_key.prefix,
                created=datetime2str(test_api_key.created),
                rate=test_api_key.rate,
                expiry_date=None,
                revoked=test_api_key.revoked,
            )
        ]
    )
    assert service_response == transaction_details_dto
