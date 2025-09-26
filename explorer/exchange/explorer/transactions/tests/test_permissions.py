import pytest
from django.conf import settings
from django.urls import reverse

from ...utils.test import NON_LOCALHOST_CLIENT, APIKeyMock


@pytest.mark.permission
def test_get_transaction_details_api_with_no_api_key_should_return_403(client):
    url = reverse('transactions:transaction_details',
                  kwargs={'network': 'BTC',
                          'tx_hash': 'a1bacbfccf58327990c37ce349d2d798ffba8aad7ef7d37069bf0ef827d974d0'})

    headers = {'REMOTE_ADDR': NON_LOCALHOST_CLIENT}
    response = client.get(url, **headers)
    assert response.status_code == 403


@pytest.mark.permission
def test_get_transaction_details_api_exceeding_rate_limit_should_return_429(client, mocker):
    url = reverse('transactions:transaction_details',
                  kwargs={'network': 'BTC',
                          'tx_hash': 'a1bacbfccf58327990c37ce349d2d798ffba8aad7ef7d37069bf0ef827d974d0'})
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    mocker.patch('exchange.explorer.authentication.services.throttling.APIKeyRateThrottle.allow_request',
                 return_value=False)
    mocker.patch('exchange.explorer.authentication.services.throttling.APIKeyRateThrottle.wait', return_value=60)
    headers = {'REMOTE_ADDR': NON_LOCALHOST_CLIENT, settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == 429


@pytest.mark.permission
def test_get_batch_transaction_details_api_with_no_api_key_should_return_403(client):
    url = reverse('transactions:batch_transaction_details', kwargs={'network': 'BTC'})

    headers = {'REMOTE_ADDR': NON_LOCALHOST_CLIENT}
    data = {'tx_hashes': ['a1bacbfccf58327990c37ce349d2d798ffba8aad7ef7d37069bf0ef827d974d0',
                          'c7505c6895649ea2aab924895ffe3a59af71eb94c2ed98b15aee0fb6b543a118']}
    response = client.post(url, data, content_type='application/json', **headers)
    assert response.status_code == 403


@pytest.mark.permission
def test_get_batch_transaction_details_api_exceeding_rate_limit_should_return_429(client, mocker):
    url = reverse('transactions:batch_transaction_details', kwargs={'network': 'BTC'})
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    mocker.patch('exchange.explorer.authentication.services.throttling.APIKeyRateThrottle.allow_request',
                 return_value=False)
    mocker.patch('exchange.explorer.authentication.services.throttling.APIKeyRateThrottle.wait', return_value=60)
    headers = {'REMOTE_ADDR': NON_LOCALHOST_CLIENT, settings.API_KEY_CUSTOM_HEADER: 'key'}
    data = {'tx_hashes': ['a1bacbfccf58327990c37ce349d2d798ffba8aad7ef7d37069bf0ef827d974d0',
                          'c7505c6895649ea2aab924895ffe3a59af71eb94c2ed98b15aee0fb6b543a118']}
    response = client.post(url, data, content_type='application/json', **headers)
    assert response.status_code == 429
