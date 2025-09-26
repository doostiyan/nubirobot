import pytest
from django.conf import settings
from django.urls import reverse

from ...utils.test import APIKeyMock


@pytest.mark.skip
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize('network, address, currency',
                         [
                             ('ETH', '0x9c148d6572a96be1ed8e30a2912ec641f40d921d', 'ETH'),  # Account based
                             # ('DOGE', 'DE5opaXjFgDhFBqL6tBDxTAQ56zkX6EToX', 'DOGE'),  # UTXO
                         ])
def test_get_wallet_balance_api_for_all_symbols_and_networks(network, address, currency, client, mocker):
    url = reverse('wallets:wallet_balance',
                  kwargs={'network': network,
                          'address': address})
    if currency:
        url += '?currency={}'.format(currency)

    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == 200


@pytest.mark.view
@pytest.mark.django_db
def test_get_wallet_balance_api_with_invalid_network_should_return_404(client, mocker):
    url = reverse('wallets:wallet_balance',
                  kwargs={'network': 'INVALID_NETWORK',
                          'address': 'bc1qh6q7u6sh8428ly763yczrv4s4ngjuavdx3dwjw'})
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == 400


@pytest.mark.view
@pytest.mark.django_db
def test_get_wallet_balance_api_with_invalid_address_should_return_400(client, mocker):
    url = reverse('wallets:wallet_balance',
                  kwargs={'network': 'ETH',
                          'address': 'INVALID_ADDRESS'})
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == 400

@pytest.mark.skip
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize('network, addresses, currency',
                         [
                             ('ETH', ['0x9c148d6572a96be1ed8e30a2912ec641f40d921d',
                                      '0x70ac6efc1776fcd4011baed6520b1556a672605a'], 'ETH'),
                             # Account based
                             # ('DOGE', ['DE5opaXjFgDhFBqL6tBDxTAQ56zkX6EToX',
                             #           'DCSHdVLyjx58AbzJ7FAbD52SyULfpepRrs'], 'DOGE'),
                             # UTXO
                         ])
def test_get_batch_wallet_balance_api_for_all_symbols_and_networks(network, addresses, currency, client, mocker):
    url = reverse('wallets:batch_wallet_balance', kwargs={'network': network})
    if currency:
        url += '?currency={}'.format(currency)

    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    data = {'addresses': addresses, 'currency': currency}
    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.post(url, data, content_type='application/json', **headers)
    assert response.status_code == 200


@pytest.mark.view
@pytest.mark.django_db
def test_get_batch_wallet_balance_api_with_invalid_network_should_return_404(client, mocker):
    url = reverse('wallets:batch_wallet_balance', kwargs={'network': 'INVALID_NETWORK'})
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    data = {'addresses': ['bc1qh6q7u6sh8428ly763yczrv4s4ngjuavdx3dwjw',
                          '1KNm4K8GUK8sMoxc2Z3zU8Uv5FDVjrA72p'], 'currency': 'BTC'}
    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.post(url, data, content_type='application/json', **headers)
    assert response.status_code == 404


@pytest.mark.view
@pytest.mark.django_db
def test_get_batch_wallet_balance_api_with_invalid_address_should_return_400(client, mocker):
    url = reverse('wallets:batch_wallet_balance', kwargs={'network': 'ETH'})
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    data = {'addresses': ['INVALID_ADDRESS1', 'INVALID_ADDRESS2'], 'currency': 'BTC'}
    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.post(url, data, content_type='application/json', **headers)
    assert response.status_code == 400


@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize('network, address, currency',
                         [
                             ('ETH', '0x9c148d6572a96be1ed8e30a2912ec641f40d921d', 'ETH'),  # Account based
                             # ('DOGE', 'DE5opaXjFgDhFBqL6tBDxTAQ56zkX6EToX', 'DOGE'),  # UTXO
                         ])
def test_get_wallet_transactions_api_for_all_symbols_and_networks(network, address, currency, client, mocker):
    url = reverse('wallets:wallet_transactions',
                  kwargs={'network': network,
                          'address': address})
    if currency:
        url += '?currency={}'.format(currency)

    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == 200


@pytest.mark.view
@pytest.mark.django_db
def test_get_wallet_transactions_api_with_invalid_address_should_return_400(client, mocker):
    url = reverse('wallets:wallet_transactions',
                  kwargs={'network': 'ETH',
                          'address': 'INVALID_ADDRESS'})
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == 404


@pytest.mark.view
@pytest.mark.django_db
def test_get_wallet_transactions_api_with_invalid_network_should_return_404(client, mocker):
    url = reverse('wallets:wallet_transactions',
                  kwargs={'network': 'INVALID_NETWORK',
                          'address': 'bc1qh6q7u6sh8428ly763yczrv4s4ngjuavdx3dwjw'})
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == 404
