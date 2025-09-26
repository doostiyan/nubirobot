import pytest
from django.conf import settings
from django.urls import reverse

from ...utils.test import NON_LOCALHOST_CLIENT, APIKeyMock


@pytest.mark.permission
def test_get_wallet_balance_api_with_no_api_key_should_return_403(client):
    url = reverse('wallets:wallet_balance',
                  kwargs={'network': 'BTC',
                          'address': 'bc1qh6q7u6sh8428ly763yczrv4s4ngjuavdx3dwjw'})
    headers = {'REMOTE_ADDR': NON_LOCALHOST_CLIENT}
    response = client.get(url, **headers)
    assert response.status_code == 403


@pytest.mark.permission
def test_get_wallet_transactions_api_exceeding_rate_limit_should_return_429(client, mocker):
    url = reverse('wallets:wallet_balance',
                  kwargs={'network': 'BTC',
                          'address': 'bc1qh6q7u6sh8428ly763yczrv4s4ngjuavdx3dwjw'})
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    mocker.patch('exchange.explorer.authentication.services.throttling.APIKeyRateThrottle.allow_request',
                 return_value=False)
    mocker.patch('exchange.explorer.authentication.services.throttling.APIKeyRateThrottle.wait', return_value=60)
    headers = {'REMOTE_ADDR': NON_LOCALHOST_CLIENT, settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == 429


@pytest.mark.permission
def test_get_batch_wallet_balance_api_with_no_api_key_should_return_403(client):
    url = reverse('wallets:batch_wallet_balance', kwargs={'network': 'BTC'})
    headers = {'REMOTE_ADDR': NON_LOCALHOST_CLIENT}
    data = {'addresses': ['bc1qh6q7u6sh8428ly763yczrv4s4ngjuavdx3dwjw', 'bc1qh6q7u6sh8428ly763yczrv4s4ngjuavdx3dwjw']}
    response = client.post(url, data, content_type='application/json', **headers)
    assert response.status_code == 403


@pytest.mark.permission
def test_get_batch_wallet_transactions_api_exceeding_rate_limit_should_return_429(client, mocker):
    url = reverse('wallets:batch_wallet_balance', kwargs={'network': 'BTC'})
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    mocker.patch('exchange.explorer.authentication.services.throttling.APIKeyRateThrottle.allow_request',
                 return_value=False)
    mocker.patch('exchange.explorer.authentication.services.throttling.APIKeyRateThrottle.wait', return_value=60)
    headers = {'REMOTE_ADDR': NON_LOCALHOST_CLIENT, settings.API_KEY_CUSTOM_HEADER: 'key'}
    data = {'addresses': ['bc1qh6q7u6sh8428ly763yczrv4s4ngjuavdx3dwjw', 'bc1qh6q7u6sh8428ly763yczrv4s4ngjuavdx3dwjw']}
    response = client.post(url, data, content_type='application/json', **headers)
    assert response.status_code == 429


@pytest.mark.permission
def test_get_wallet_transactions_api_with_no_api_key_should_return_403(client):
    url = reverse('wallets:wallet_transactions',
                  kwargs={'network': 'BTC',
                          'address': 'bc1qh6q7u6sh8428ly763yczrv4s4ngjuavdx3dwjw'})
    headers = {'REMOTE_ADDR': NON_LOCALHOST_CLIENT}
    response = client.get(url, **headers)
    assert response.status_code == 403


@pytest.mark.permission
def test_get_wallet_balance_api_exceeding_rate_limit_should_return_429(client, mocker):
    url = reverse('wallets:wallet_transactions',
                  kwargs={'network': 'BTC',
                          'address': 'bc1qh6q7u6sh8428ly763yczrv4s4ngjuavdx3dwjw'})
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    mocker.patch('exchange.explorer.authentication.services.throttling.APIKeyRateThrottle.allow_request',
                 return_value=False)
    mocker.patch('exchange.explorer.authentication.services.throttling.APIKeyRateThrottle.wait', return_value=60)
    headers = {'REMOTE_ADDR': NON_LOCALHOST_CLIENT, settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == 429
