import pytest
from django.conf import settings
from django.urls import reverse
from django.utils.http import urlencode

from ...utils.test import NON_LOCALHOST_CLIENT, APIKeyMock


@pytest.mark.permission
def test_get_latest_block_info_dto_api_with_no_api_key_should_return_403(client):
    url = reverse('blocks:block_info',
                  kwargs={'network': 'BTC'})
    query_params = {'after_block_number': 50, 'to_block_number': 60}
    url = f'{url}?{urlencode(query_params)}'
    headers = {'REMOTE_ADDR': NON_LOCALHOST_CLIENT}
    response = client.get(url, **headers)
    assert response.status_code == 403


@pytest.mark.permission
def test_get_get_latest_block_info_api_exceeding_rate_limit_should_return_429(client, mocker):
    url = reverse('blocks:block_info',
                  kwargs={'network': 'BTC'})
    query_params = {'after_block_number': 50, 'to_block_number': 60}
    url = f'{url}?{urlencode(query_params)}'
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    mocker.patch('exchange.explorer.authentication.services.throttling.APIKeyRateThrottle.allow_request',
                 return_value=False)
    mocker.patch('exchange.explorer.authentication.services.throttling.APIKeyRateThrottle.wait', return_value=60)
    headers = {'REMOTE_ADDR': NON_LOCALHOST_CLIENT, settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == 429


@pytest.mark.permission
def test_get_block_head_api_with_no_api_key_should_return_403(client):
    url = reverse('blocks:block_head',
                  kwargs={'network': 'BTC'})
    headers = {'REMOTE_ADDR': NON_LOCALHOST_CLIENT}
    response = client.get(url, **headers)
    assert response.status_code == 403


@pytest.mark.permission
def test_get_block_head_api_exceeding_rate_limit_should_return_429(client, mocker):
    url = reverse('blocks:block_head',
                  kwargs={'network': 'BTC'})
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    mocker.patch('exchange.explorer.authentication.services.throttling.APIKeyRateThrottle.allow_request',
                 return_value=False)
    mocker.patch('exchange.explorer.authentication.services.throttling.APIKeyRateThrottle.wait', return_value=60)
    headers = {'REMOTE_ADDR': NON_LOCALHOST_CLIENT, settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == 429
