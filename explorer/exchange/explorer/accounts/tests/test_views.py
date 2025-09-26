from urllib.parse import urlencode

import pytest
from django.urls import reverse
from rest_framework import status

from ...authentication.models import UserAPIKey
from ..models import User
from ..services import delete_api_key


@pytest.mark.view
@pytest.mark.django_db
def test_delete_api_key(client):
    # test for revoked api key
    username, password, email = 'test', 'testPassword', 'test@gmail.com'
    user = User.objects.create_user(username=username, email=email, password=password)
    api_key, _ = UserAPIKey.objects.create_key(name='valid_api_key', user=user, rate='8/min')
    delete_api_key(api_key.prefix)
    api_key.refresh_from_db()
    assert api_key.revoked is True

    # get jwt for authorization
    user.is_staff = True
    user.save()
    login_url = reverse('authentication:token_obtain_pair')
    get_token_response = client.post(login_url, {'username': username, 'password': password})
    assert get_token_response.status_code == status.HTTP_200_OK

    # set header for authorization
    data = get_token_response.json()
    valid_token = data.get('access')
    headers = {
        'Authorization': 'Bearer ' + valid_token,
        'Content-Type': 'application/json'
    }

    # test for api key is valid or not
    query_params = {'api_key': api_key}
    delete_api_key_url = f'{reverse("accounts:user_api_keys")}?{urlencode(query_params)}'
    response = client.delete(delete_api_key_url, headers=headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND
