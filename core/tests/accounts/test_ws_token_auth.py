import hashlib
from unittest.mock import patch

import jwt
import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

WEBSOCKET_AUTH_SECRET = '''-----BEGIN EC PRIVATE KEY-----
MIHcAgEBBEIAuVux2BkQfDNVHQjAFplRVZ/c6ywkURjeltIKU9v72izXNwJn8Jz0
acgdt5nevzFk4z0b3fd8nw0HpDharocK05mgBwYFK4EEACOhgYkDgYYABABUFh1z
UGPYS9WrOx3aVnHlemGGnW4a/GHYF0cxPV40KSVHhBWVfCFpjKTR5qDw/7gd7sAz
d8avlJA3TZwKJWGSIQBD96+TnEDs3h50z9VDxY1erDVqGDkMWvcsotUB6ICIEWMs
uDItN6DEab9QMZ8mwWRj5Ys5TbgnyZf5MY54/2TWKw==
-----END EC PRIVATE KEY-----'''

WEBSOCKET_AUTH_PUBKEY = '''-----BEGIN PUBLIC KEY-----
MIGbMBAGByqGSM49AgEGBSuBBAAjA4GGAAQAVBYdc1Bj2EvVqzsd2lZx5Xphhp1u
Gvxh2BdHMT1eNCklR4QVlXwhaYyk0eag8P+4He7AM3fGr5SQN02cCiVhkiEAQ/ev
k5xA7N4edM/VQ8WNXqw1ahg5DFr3LKLVAeiAiBFjLLgyLTegxGm/UDGfJsFkY+WL
OU24J8mX+TGOeP9k1is=
-----END PUBLIC KEY-----'''


@override_settings(WEBSOCKET_AUTH_SECRET=WEBSOCKET_AUTH_SECRET)
@patch('exchange.base.http.get_client_ip', return_value='127.0.0.1')
@patch('time.time', return_value=1234567890)
@pytest.mark.django_db
def test_websocket_auth_token_generation(mock_time, mock_get_client_ip, django_user_model):
    test_user = django_user_model.objects.get(pk=201)
    client = APIClient()
    client.force_authenticate(user=test_user)

    response = client.get('/auth/ws/token/')

    assert response.status_code == status.HTTP_200_OK
    assert 'token' in response.data
    assert response.data['status'] == 'ok'

    token = response.data['token']

    decoded_payload = jwt.decode(token, WEBSOCKET_AUTH_PUBKEY, algorithms=['ES512'], options={'verify_exp': False})

    hash_of_user_uid = hashlib.sha256(test_user.uid.bytes).hexdigest()
    # Validate the token payload
    assert decoded_payload['sub'] == hash_of_user_uid[:32]
    assert decoded_payload['iat'] == int(mock_time.return_value)
    assert decoded_payload['exp'] == int(mock_time.return_value) + 1200
