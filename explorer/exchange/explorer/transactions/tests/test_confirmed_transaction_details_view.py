from datetime import timedelta
from unittest.mock import patch

import pytest
from config.models import Currencies
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from exchange.explorer.networkproviders.dtos.provider import ProviderData
from exchange.explorer.networkproviders.tests.fixtures.provider_fixtures import provider_data
from exchange.explorer.transactions.models import Transfer
from exchange.explorer.transactions.tests.fixtures.tx_details_fixtures import (
    address,
    get_txs_incoming_tx,
    persisted_transfer,
    persisted_transfer__same_to_address__different_hash,
    token_tx_details,
    tx_details,
    tx_details_without_date,
    tx_hash,
)

pytestmark = pytest.mark.django_db


def test__get_transactions__when_address_is_none__return_404(client: APIClient):
    url = reverse('transactions:confirmed_transaction_details', kwargs={'network': 'ETH', 'tx_hash': None})

    response = client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test__get_transactions__when_network_is_none__return_404(client: APIClient, tx_hash: str):
    url = reverse('transactions:confirmed_transaction_details', kwargs={'network': None, 'tx_hash': tx_hash})

    response = client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@patch(
    'exchange.explorer.networkproviders.services.network_default_provider_service'
    '.NetworkDefaultProviderService.load_default_provider_data')
def test__transaction_details__when_in_db__return_transfer(
        mock_load_provider,
        client: APIClient,
        persisted_transfer: Transfer,
        provider_data: ProviderData):
    mock_load_provider.return_value = provider_data
    url = reverse(
        'transactions:confirmed_transaction_details',
        kwargs={'network': 'ETH', 'tx_hash': persisted_transfer.tx_hash}
    )

    response = client.get(url, data={'currency': 'USDT'})
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]['symbol'] == 'USDT'
    assert response.data[0]['from_address'] == persisted_transfer.from_address_str
    assert response.data[0]['to_address'] == persisted_transfer.to_address_str
    assert response.data[0]['tx_hash'] == persisted_transfer.tx_hash
    assert response.data[0]['success'] == persisted_transfer.success
    assert response.data[0]['value'] == persisted_transfer.value
    assert response.data[0]['block_height'] == persisted_transfer.block_height
    assert response.data[0]['block_hash'] == persisted_transfer.block_hash
    assert response.data[0]['date'] == (persisted_transfer.date - timedelta(hours=3, minutes=30)).isoformat() + 'Z'
    assert response.data[0]['tx_fee'] == persisted_transfer.tx_fee
    assert response.data[0]['token'] == persisted_transfer.token


@patch(
    'exchange.explorer.networkproviders.services.network_default_provider_service'
    '.NetworkDefaultProviderService.load_default_provider_data')
def test__tx_details__when_not_in_db__return_successful(
        mock_load_provider,
        client: APIClient,
        tx_hash: str,
        provider_data: ProviderData,
        address: str,
        persisted_transfer__same_to_address__different_hash: Transfer,
        tx_details: dict,
        get_txs_incoming_tx: dict):
    mock_load_provider.return_value = provider_data
    url = reverse('transactions:confirmed_transaction_details', kwargs={'network': 'ETH', 'tx_hash': tx_hash})

    with patch(
            'exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_tx_details'
    ) as mock_tx_details:
        mock_tx_details.return_value = tx_details
        with patch('exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_txs') as mock_txs:
            mock_txs.return_value = [{Currencies.eth: get_txs_incoming_tx}]

            response = client.get(url, data={'address': address})
            assert response.status_code == status.HTTP_200_OK
            got_tx = response.json()[0]
            assert got_tx['to_address'] == address
            assert got_tx['success']
            assert got_tx['tx_hash'] == tx_hash
            assert response.data[0]['from_address'] == get_txs_incoming_tx['from_address']
            assert response.data[0]['value'] == str(get_txs_incoming_tx['amount'])
            assert response.data[0]['block_height'] == get_txs_incoming_tx['block']
            assert response.data[0]['symbol'] == 'ETH'
            assert response.data[0]['confirmations'] == get_txs_incoming_tx['confirmations']
            assert response.data[0]['date'] == get_txs_incoming_tx['date'].isoformat() + 'Z'


@patch(
    'exchange.explorer.networkproviders.services.network_default_provider_service'
    '.NetworkDefaultProviderService.load_default_provider_data')
def test__token_tx_details__when_not_in_db__return_successful(
        mock_load_provider,
        client: APIClient,
        tx_hash: str,
        provider_data: ProviderData,
        address: str,
        persisted_transfer__same_to_address__different_hash: Transfer,
        tx_details: dict,
        get_txs_incoming_tx: dict,
        token_tx_details: dict):
    mock_load_provider.return_value = provider_data
    url = reverse('transactions:confirmed_transaction_details', kwargs={'network': 'ETH', 'tx_hash': tx_hash})

    with patch(
            'exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_token_tx_details'
    ) as mock_tx_details:
        mock_tx_details.return_value = token_tx_details
        with patch('exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_token_txs') as mock_txs:
            mock_txs.return_value = [{Currencies.usdt: get_txs_incoming_tx}]

            response = client.get(url, data={'address': address, 'currency': 'USDT'})
            assert response.status_code == status.HTTP_200_OK
            got_tx = response.json()[0]
            assert got_tx['to_address'] == address
            assert got_tx['success']
            assert got_tx['tx_hash'] == tx_hash
            assert got_tx['symbol'] == 'USDT'


@patch(
    'exchange.explorer.networkproviders.services.network_default_provider_service'
    '.NetworkDefaultProviderService.load_default_provider_data')
def test__tx_details__when_not_in_db_and_address_not_provided__returns_404(
        mock_load_provider,
        provider_data: ProviderData,
        client: APIClient,
        tx_hash: str
):
    mock_load_provider.return_value = provider_data
    url = reverse('transactions:confirmed_transaction_details', kwargs={'network': 'ETH', 'tx_hash': tx_hash})

    response = client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@patch(
    'exchange.explorer.networkproviders.services.network_default_provider_service'
    '.NetworkDefaultProviderService.load_default_provider_data')
def test__tx_details__when_not_in_db_and_date_not_in_response__returns_404(
        mock_load_provider,
        provider_data: ProviderData,
        client: APIClient,
        tx_hash: str,
        tx_details_without_date: dict):
    mock_load_provider.return_value = provider_data
    url = reverse('transactions:confirmed_transaction_details', kwargs={'network': 'ETH', 'tx_hash': tx_hash})
    with patch(
            'exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_tx_details'
    ) as mock_tx_details:
        mock_tx_details.return_value = tx_details_without_date
        response = client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@patch(
    'exchange.explorer.networkproviders.services.network_default_provider_service'
    '.NetworkDefaultProviderService.load_default_provider_data')
def test__tx_details__when_not_in_db_and_to_address_not_in_db__returns_404(
        mock_load_provider,
        provider_data: ProviderData,
        client: APIClient,
        tx_hash: str,
        tx_details: dict):
    mock_load_provider.return_value = provider_data
    url = reverse('transactions:confirmed_transaction_details', kwargs={'network': 'ETH', 'tx_hash': tx_hash})
    with patch(
            'exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_tx_details'
    ) as mock_tx_details:
        mock_tx_details.return_value = tx_details
        response = client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
