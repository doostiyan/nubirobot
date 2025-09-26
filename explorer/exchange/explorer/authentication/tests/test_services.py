import time

import pytest
import django_redis
from unittest.mock import MagicMock
from django.conf import settings
from django.urls import reverse

from ...utils.test import NON_LOCALHOST_CLIENT, APIKeyMock


@pytest.mark.service
@pytest.mark.django_db
def test_exceeding_rate_limit_should_return_429(client, mocker):
    url = reverse('transactions:transaction_details',
                  kwargs={'network': 'BTC',
                          'tx_hash': 'a1bacbfccf58327990c37ce349d2d798ffba8aad7ef7d37069bf0ef827d974d0'})
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch('exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key', return_value=api_key)
    mocker.patch('exchange.explorer.authentication.services.throttling.APIKeyRateThrottle.cache.set', return_value=None)
    mocker.patch('exchange.explorer.authentication.services.throttling.APIKeyRateThrottle.cache.get',
                 return_value=[time.time(), time.time()])
    mocker.patch('exchange.explorer.authentication.services.throttling.APIKeyRateThrottle.wait', return_value=60)
    headers = {'REMOTE_ADDR': NON_LOCALHOST_CLIENT, settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == 429
