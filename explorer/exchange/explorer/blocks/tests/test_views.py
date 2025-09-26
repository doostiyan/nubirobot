import pytest
from django.conf import settings
from django.urls import reverse
from django.utils.http import urlencode

from ...utils.test import APIKeyMock, setup_prod


@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize('network, after_block_number, to_block_number',
                         [
                             # ('DOGE', 50, 60),  # UTXO
                             ('ETH', 50, 60),  # Account based
                         ])
def test_get_block_info_api_for_all_networks(network, after_block_number, to_block_number, client, mocker, setup_prod):
    url = reverse('blocks:block_info', kwargs={'network': network})
    query_params = {'after_block_number': after_block_number, 'to_block_number': to_block_number}
    url = f'{url}?{urlencode(query_params)}'

    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == 200


@pytest.mark.view
@pytest.mark.django_db
def test_get_block_info_api_with_invalid_network_should_return_404(client, mocker):
    url = reverse('blocks:block_info',
                  kwargs={'network': 'INVALID_NETWORK'})
    query_params = {'after_block_number': 50, 'to_block_number': 60, 'client': 'test'}
    url = f'{url}?{urlencode(query_params)}'
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == 404


@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize('network',
                         [
                             'APT',  # UTXO
                             # 'FIL',  # Account based
                         ])
def test_get_block_head_api_for_all_networks(network, client, mocker, setup_prod):
    url = reverse('blocks:block_head', kwargs={'network': network})
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == 200


@pytest.mark.view
@pytest.mark.django_db
def test_get_block_head_api_with_invalid_network_should_return_404(client, mocker):
    url = reverse('blocks:block_head',
                  kwargs={'network': 'INVALID_NETWORK'})
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == 404
