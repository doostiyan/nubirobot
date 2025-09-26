from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from exchange.explorer.networkproviders.dtos.provider import ProviderData
from exchange.explorer.networkproviders.tests.fixtures.provider_fixtures import provider_data
from exchange.explorer.transactions.tests.fixtures.tx_details_fixtures import (
    address,
    token_tx_details,
    token_tx_details_with_second_hash,
    tx_details,
    tx_details_with_second_hash,
    tx_hash,
    tx_hash_second,
)

pytestmark = pytest.mark.django_db


def test__get_transactions__when_network_is_none__return_404(client: APIClient):
    url = reverse('transactions:batch_transaction_details', kwargs={'network': None})

    response = client.get(url)
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@patch(
    'exchange.explorer.networkproviders.services.network_default_provider_service'
    '.NetworkDefaultProviderService.load_default_provider_data')
def test__batch_tx_details__return_successful(
        mock_load_provider,
        client: APIClient,
        tx_hash: str,
        tx_hash_second: str,
        provider_data: ProviderData,
        tx_details: dict,
        tx_details_with_second_hash: dict):
    mock_load_provider.return_value = provider_data
    url = reverse('transactions:batch_transaction_details', kwargs={'network': 'ETH'})

    with patch(
            'exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_tx_details'
    ) as mock_tx_details:
        mock_tx_details.side_effect = [(tx_details), (tx_details_with_second_hash)]

        response = client.post(url, data={'tx_hashes': [tx_hash, tx_hash_second]}, format='json')
        assert response.status_code == status.HTTP_200_OK
        got_first_tx = response.json()['transactions'][0]
        got_second_tx = response.json()['transactions'][1]
        assert got_first_tx['success']
        assert got_first_tx['tx_hash'] == tx_hash
        assert got_first_tx['from_address'] == tx_details['transfers'][0]['from']
        assert got_first_tx['to_address'] == tx_details['transfers'][0]['to']
        assert got_first_tx['value'] == str(tx_details['transfers'][0]['value'])
        assert got_first_tx['symbol'] == tx_details['transfers'][0]['symbol']
        assert got_first_tx['confirmations'] == tx_details['confirmations']
        assert got_first_tx['block_height'] == tx_details['block']
        assert got_first_tx['date'] == tx_details['date'].isoformat() + 'Z'

        assert got_second_tx['success']
        assert got_second_tx['tx_hash'] == tx_hash_second
        assert got_first_tx['from_address'] == tx_details_with_second_hash['transfers'][0]['from']
        assert got_first_tx['to_address'] == tx_details_with_second_hash['transfers'][0]['to']
        assert got_first_tx['value'] == str(tx_details_with_second_hash['transfers'][0]['value'])
        assert got_first_tx['symbol'] == tx_details_with_second_hash['transfers'][0]['symbol']
        assert got_first_tx['confirmations'] == tx_details_with_second_hash['confirmations']
        assert got_first_tx['block_height'] == tx_details_with_second_hash['block']
        assert got_first_tx['date'] == tx_details_with_second_hash['date'].isoformat() + 'Z'



@patch(
    'exchange.explorer.networkproviders.services.network_default_provider_service'
    '.NetworkDefaultProviderService.load_default_provider_data')
def test__batch_token_tx_details__return_successful(
        mock_load_provider,
        client: APIClient,
        tx_hash: str,
        tx_hash_second: str,
        provider_data: ProviderData,
        token_tx_details_with_second_hash: dict,
        token_tx_details: dict):
    mock_load_provider.return_value = provider_data
    url = reverse('transactions:batch_transaction_details', kwargs={'network': 'ETH'})

    with patch(
            'exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_token_tx_details'
    ) as mock_tx_details:
        mock_tx_details.side_effect = [token_tx_details, token_tx_details_with_second_hash]

        response = client.post(f'{url}?currency=USDT', data={'tx_hashes': [tx_hash, tx_hash_second]})
        assert response.status_code == status.HTTP_200_OK
        got_first_tx = response.json()['transactions'][0]
        got_second_tx = response.json()['transactions'][1]
        assert got_first_tx['success']
        assert got_first_tx['tx_hash'] == tx_hash
        assert got_first_tx['from_address'] == token_tx_details['transfers'][0]['from']
        assert got_first_tx['to_address'] == token_tx_details['transfers'][0]['to']
        assert got_first_tx['value'] == str(token_tx_details['transfers'][0]['value'])
        assert got_first_tx['symbol'] == token_tx_details['transfers'][0]['symbol']
        assert got_first_tx['confirmations'] == token_tx_details['confirmations']
        assert got_first_tx['block_height'] == token_tx_details['block']
        assert got_first_tx['date'] == token_tx_details['date'].isoformat() + 'Z'

        assert got_second_tx['success']
        assert got_second_tx['tx_hash'] == tx_hash_second
        assert got_first_tx['from_address'] == token_tx_details_with_second_hash['transfers'][0]['from']
        assert got_first_tx['to_address'] == token_tx_details_with_second_hash['transfers'][0]['to']
        assert got_first_tx['value'] == str(token_tx_details_with_second_hash['transfers'][0]['value'])
        assert got_first_tx['symbol'] == token_tx_details_with_second_hash['transfers'][0]['symbol']
        assert got_first_tx['confirmations'] == token_tx_details_with_second_hash['confirmations']
        assert got_first_tx['block_height'] == token_tx_details_with_second_hash['block']
        assert got_first_tx['date'] == token_tx_details_with_second_hash['date'].isoformat() + 'Z'

