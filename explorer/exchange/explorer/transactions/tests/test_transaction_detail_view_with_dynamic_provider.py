from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from dateutil.parser import isoparse
from django.test.client import Client
from django.urls import reverse
from rest_framework import status

from .fixtures.explorer_interface_fixtures import ada_explorer_interface
from .fixtures.request_fixtures import api_key_fixture, auth_headers


@pytest.mark.view
@pytest.mark.django_db
def test__transaction_detail_view__dynamic_provider_passing__successful(
        client, api_key_fixture, ada_explorer_interface: MagicMock, auth_headers: dict) -> None:
    url = reverse(viewname='transactions:transaction_details', kwargs={
        'network': 'ADA',
        'tx_hash': '8d5057bdaf6117621641b5f737a800286c00616b24d93cb68e166d4fb6851d38',
    })

    params = {
        'provider_name': 'cardano_polaris_graphql_api',
        'base_url': 'https://graphql.cardano.polaristech.ir',
    }

    response = client.get(url, data=params, **auth_headers)

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert isinstance(response_data, list)
    tx = response_data[0]

    assert tx['tx_hash'] == ada_explorer_interface.hash
    assert tx['success'] == ada_explorer_interface.success
    assert tx['block_height'] == ada_explorer_interface.block
    assert tx['confirmations'] == ada_explorer_interface.confirmations
    assert Decimal(tx['tx_fee']) == ada_explorer_interface.fees
    assert isoparse(tx['date']) == ada_explorer_interface.date
    assert str(ada_explorer_interface.transfers[0].get('value')) == tx['value']


@pytest.mark.django_db
def test__transaction_details__with_malformed_base_url__failed(client: Client, auth_headers: dict) -> None:
    url = reverse(viewname='transactions:transaction_details', kwargs={
        'network': 'ADA',
        'tx_hash': '8d5057bdaf6117621641b5f737a800286c00616b24d93cb68e166d4fb6851d38',
    })

    params = {
        'provider_name': 'cardano_polaris_graphql_api',
        'base_url': 'https://bad-url',
    }

    response = client.get(url, data=params, **auth_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'base_url' in response.json()['detail']


@pytest.mark.django_db
def test__transaction_details__with_malformed_network__failed(client: Client, auth_headers: dict) -> None:
    url = reverse(viewname='transactions:transaction_details', kwargs={
        'network': 'TEST',
        'tx_hash': '8d5057bdaf6117621641b5f737a800286c00616b24d93cb68e166d4fb6851d38',
    })

    params = {
        'provider_name': 'cardano_polaris_graphql_api',
        'base_url': 'https://graphql.cardano.polaristech.ir',
    }

    response = client.get(url, data=params, **auth_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'network' in response.json()['detail']
