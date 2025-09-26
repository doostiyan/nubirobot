from datetime import timedelta
from typing import Any, Dict
from unittest.mock import patch

import pytest
from config.models import Currencies
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from exchange.explorer.networkproviders.dtos.provider import ProviderData
from exchange.explorer.transactions.models import Transfer
from exchange.explorer.wallets.tests.fixtures.transfer_fixtures import (
    address,
    get_txs_incoming_tx,
    get_txs_incoming_tx__less_then_min_value,
    get_txs_incoming_tx_different_hash,
    get_txs_outgoing_tx,
    persisted_transfer,
)

from .fixtures.provider_fixtures import provider_data

pytestmark = pytest.mark.django_db


def test__get_transactions__when_address_is_none__return_404(client: APIClient):
    url = reverse('wallets:wallet_transactions', kwargs={'network': 'ETH', 'address': None})

    response = client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test__get_transactions__when_network_is_none__return_404(client: APIClient, address: str):
    url = reverse('wallets:wallet_transactions', kwargs={'network': None, 'address': address})

    response = client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@patch(
    'exchange.explorer.networkproviders.services.network_default_provider_service'
    '.NetworkDefaultProviderService.load_default_provider_data')
def test__get_transactions__when_currency_set__return_filtered(
        mock_load_provider,
        client: APIClient,
        address: str,
        provider_data: ProviderData,
        get_txs_incoming_tx: Dict[str, Any],
        get_txs_incoming_tx_different_hash: Dict[str, Any]):
    mock_load_provider.return_value = provider_data
    url = reverse('wallets:wallet_transactions', kwargs={'network': 'ETH', 'address': address})

    with patch(
            'exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_token_txs'
    ) as mock_get_token_txs:
        mock_get_token_txs.return_value = [
            {
                Currencies.usdt: get_txs_incoming_tx
            },
            {
                Currencies.btc: get_txs_incoming_tx_different_hash
            }
        ]

        response = client.get(url, data={'currency': 'USDT'})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['symbol'] == 'USDT'
        assert response.data[0]['tx_hash'] == get_txs_incoming_tx['hash']
        assert response.data[0]['from_address'] == get_txs_incoming_tx['from_address']
        assert response.data[0]['to_address'] == get_txs_incoming_tx['to_address']
        assert response.data[0]['value'] == str(get_txs_incoming_tx['amount'])
        assert response.data[0]['success']
        assert response.data[0]['confirmations'] == get_txs_incoming_tx['confirmations']
        assert response.data[0]['block_height'] == get_txs_incoming_tx['block']
        assert response.data[0]['date'] == get_txs_incoming_tx['date'].isoformat() + 'Z'


@patch(
    'exchange.explorer.networkproviders.services.network_default_provider_service'
    '.NetworkDefaultProviderService.load_default_provider_data')
def test__get_transactions__when_filter_not_set__return_all(
        mock_load_provider,
        client: APIClient,
        address: str,
        provider_data: ProviderData,
        get_txs_incoming_tx: Dict[str, Any],
        get_txs_incoming_tx_different_hash: Dict[str, Any]):
    mock_load_provider.return_value = provider_data
    url = reverse('wallets:wallet_transactions', kwargs={'network': 'ETH', 'address': address})

    with patch('exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_txs') as mock_get_txs:
        mock_return_value = [
            {
                Currencies.eth: get_txs_incoming_tx
            },
            {
                Currencies.eth: get_txs_incoming_tx_different_hash
            }
        ]
        mock_get_txs.return_value = mock_return_value

        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == len(mock_return_value)

        assert response.json()[0]['tx_hash'] == get_txs_incoming_tx['hash']
        assert response.json()[0]['success']
        assert response.json()[0]['from_address'] == get_txs_incoming_tx['from_address']
        assert response.json()[0]['to_address'] == get_txs_incoming_tx['to_address']
        assert response.json()[0]['value'] == str(get_txs_incoming_tx['amount'])
        assert response.json()[0]['symbol'] == 'ETH'
        assert response.json()[0]['confirmations'] == get_txs_incoming_tx['confirmations']
        assert response.json()[0]['block_height'] == get_txs_incoming_tx['block']
        assert response.json()[0]['date'] == get_txs_incoming_tx['date'].isoformat() + 'Z'

        assert response.json()[1]['tx_hash'] == get_txs_incoming_tx_different_hash['hash']
        assert response.json()[1]['success']
        assert response.json()[1]['from_address'] == get_txs_incoming_tx_different_hash['from_address']
        assert response.json()[1]['to_address'] == get_txs_incoming_tx_different_hash['to_address']
        assert response.json()[1]['value'] == str(get_txs_incoming_tx_different_hash['amount'])
        assert response.json()[1]['symbol'] == 'ETH'
        assert response.json()[1]['confirmations'] == get_txs_incoming_tx_different_hash['confirmations']
        assert response.json()[1]['block_height'] == get_txs_incoming_tx_different_hash['block']
        assert response.json()[1]['date'] == get_txs_incoming_tx_different_hash['date'].isoformat() + 'Z'


def test__get_transactions__when_tx_hash_set_and_in_db__return_single_transaction(client: APIClient,
                                                                                  persisted_transfer: Transfer):
    url = reverse('wallets:wallet_transactions',
                  kwargs={'network': 'ETH', 'address': persisted_transfer.from_address_str})

    response = client.get(url, data={'tx_hash': persisted_transfer.tx_hash})
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]['tx_hash'] == persisted_transfer.tx_hash
    assert response.data[0]['symbol'] == persisted_transfer.symbol
    assert response.data[0]['from_address'] == persisted_transfer.from_address_str
    assert response.data[0]['to_address'] == persisted_transfer.to_address_str
    assert response.data[0]['value'] == persisted_transfer.value
    assert response.data[0]['success']
    assert response.data[0]['block_height'] == persisted_transfer.block_height
    assert response.data[0]['date'] == (persisted_transfer.date - timedelta(hours=3, minutes=30)).isoformat() + 'Z'
    assert response.data[0]['confirmations'] is None
    assert response.data[0]['tx_fee'] == persisted_transfer.tx_fee
    assert response.data[0]['token'] == persisted_transfer.token


@patch(
    'exchange.explorer.networkproviders.services.network_default_provider_service'
    '.NetworkDefaultProviderService.load_default_provider_data')
def test__get_transactions__when_tx_hash_set_and_not_in_db__return_single_transaction(
        mock_load_provider,
        client: APIClient,
        address: str,
        provider_data: ProviderData,
        get_txs_incoming_tx: Dict[str, Any],
        get_txs_incoming_tx_different_hash: Dict[str, Any]):
    mock_load_provider.return_value = provider_data
    url = reverse('wallets:wallet_transactions', kwargs={'network': 'ETH', 'address': address})

    with patch('exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_txs') as mock_get_txs:
        mock_get_txs.return_value = [
            {
                Currencies.eth: get_txs_incoming_tx
            },
            {
                Currencies.eth: get_txs_incoming_tx_different_hash
            }
        ]

        response = client.get(url, data={
            'tx_hash': get_txs_incoming_tx['hash']
        })
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['symbol'] == 'ETH'
        assert response.data[0]['tx_hash'] == get_txs_incoming_tx['hash']
        assert response.data[0]['from_address'] == get_txs_incoming_tx['from_address']
        assert response.data[0]['to_address'] == get_txs_incoming_tx['to_address']
        assert response.data[0]['value'] == str(get_txs_incoming_tx['amount'])
        assert response.data[0]['success']
        assert response.data[0]['confirmations'] == get_txs_incoming_tx['confirmations']
        assert response.data[0]['block_height'] == get_txs_incoming_tx['block']
        assert response.data[0]['date'] == get_txs_incoming_tx['date'].isoformat() + 'Z'


@patch(
    'exchange.explorer.networkproviders.services.network_default_provider_service'
    '.NetworkDefaultProviderService.load_default_provider_data')
def test__get_transactions__when_tx_hash_set_and_not_exist__return_200_with_no_transactions(mock_load_provider,
                                                                                            client: APIClient,
                                                                                            address: str,
                                                                                            provider_data: ProviderData):
    mock_load_provider.return_value = provider_data

    url = reverse('wallets:wallet_transactions', kwargs={'network': 'ETH', 'address': address})

    with patch('exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_txs') as mock_get_txs:
        mock_get_txs.return_value = [{}]

        response = client.get(url, data={'tx_hash': 'nonexistent'})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0


@patch(
    'exchange.explorer.networkproviders.services.network_default_provider_service'
    '.NetworkDefaultProviderService.load_default_provider_data'
)
def test__get_transactions__when_tx_hash_and_token_currency_set_and_not_in_db__return_single_filtered_token_transaction(
        mock_load_provider,
        client: APIClient,
        address: str,
        provider_data: ProviderData,
        get_txs_outgoing_tx: Dict[str, Any]):
    mock_load_provider.return_value = provider_data

    url = reverse('wallets:wallet_transactions', kwargs={'network': 'ETH', 'address': address})

    with patch(
            'exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_token_txs') as mock_get_token_txs:
        mock_get_token_txs.return_value = [{Currencies.usdt: get_txs_outgoing_tx}]

        response = client.get(url, data={'currency': 'USDT'})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['tx_hash'] == get_txs_outgoing_tx['hash']
        assert response.data[0]['symbol'] == 'USDT'
        assert response.data[0]['from_address'] == get_txs_outgoing_tx['from_address']
        assert response.data[0]['to_address'] == ''
        assert response.data[0]['value'] == '-' + str(get_txs_outgoing_tx['amount'])
        assert response.data[0]['success']
        assert response.data[0]['confirmations'] == get_txs_outgoing_tx['confirmations']
        assert response.data[0]['block_height'] == get_txs_outgoing_tx['block']
        assert response.data[0]['date'] == get_txs_outgoing_tx['date'].isoformat() + 'Z'


@patch(
    'exchange.explorer.networkproviders.services.network_default_provider_service'
    '.NetworkDefaultProviderService.load_default_provider_data'
)
def test__get_transactions__when_direction_is_incoming__return_positive_value(mock_load_provider,
                                                                              client: APIClient,
                                                                              address: str,
                                                                              provider_data: ProviderData,
                                                                              get_txs_incoming_tx: Dict[str, Any]):
    mock_load_provider.return_value = provider_data

    url = reverse('wallets:wallet_transactions', kwargs={'network': 'ETH', 'address': address})

    with patch('exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_txs') as mock_get_txs:
        mock_get_txs.return_value = [{Currencies.eth: get_txs_incoming_tx}]

        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]['symbol'] == 'ETH'
        assert response.data[0]['tx_hash'] == get_txs_incoming_tx['hash']
        assert response.data[0]['from_address'] == get_txs_incoming_tx['from_address']
        assert response.data[0]['to_address'] == get_txs_incoming_tx['to_address']
        assert response.data[0]['value'] == str(get_txs_incoming_tx['amount'])
        assert response.data[0]['success']
        assert response.data[0]['confirmations'] == get_txs_incoming_tx['confirmations']
        assert response.data[0]['block_height'] == get_txs_incoming_tx['block']
        assert response.data[0]['date'] == get_txs_incoming_tx['date'].isoformat() + 'Z'


@patch(
    'exchange.explorer.networkproviders.services.network_default_provider_service'
    '.NetworkDefaultProviderService.load_default_provider_data'
)
def test__get_transactions__when_direction_is_outgoing__return_negative_value(mock_load_provider,
                                                                              client: APIClient,
                                                                              address: str,
                                                                              provider_data: ProviderData,
                                                                              get_txs_outgoing_tx: Dict[str, Any]):
    mock_load_provider.return_value = provider_data

    url = reverse('wallets:wallet_transactions', kwargs={'network': 'ETH', 'address': address})

    with patch('exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_txs') as mock_get_txs:
        mock_get_txs.return_value = [{Currencies.eth: get_txs_outgoing_tx}]

        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]['symbol'] == 'ETH'
        assert response.data[0]['tx_hash'] == get_txs_outgoing_tx['hash']
        assert response.data[0]['from_address'] == get_txs_outgoing_tx['from_address']
        assert response.data[0]['to_address'] == ''
        assert response.data[0]['value'] == '-' + str(get_txs_outgoing_tx['amount'])
        assert response.data[0]['success']
        assert response.data[0]['confirmations'] == get_txs_outgoing_tx['confirmations']
        assert response.data[0]['block_height'] == get_txs_outgoing_tx['block']
        assert response.data[0]['date'] == get_txs_outgoing_tx['date'].isoformat() + 'Z'


@patch(
    'exchange.explorer.networkproviders.services.network_default_provider_service'
    '.NetworkDefaultProviderService.load_default_provider_data'
)
def test__get_transactions__when_value_less_than_min_valid_tx_amount__return_0_value(
        mock_load_provider,
        client: APIClient,
        address: str,
        provider_data: ProviderData,
        get_txs_incoming_tx__less_then_min_value: Dict[str, Any]):
    mock_load_provider.return_value = provider_data

    url = reverse('wallets:wallet_transactions', kwargs={'network': 'ETH', 'address': address})

    with patch('exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_txs') as mock_get_txs:
        mock_get_txs.return_value = [{Currencies.eth: get_txs_incoming_tx__less_then_min_value}]

        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]['value'] == '0'
        assert response.data[0]['symbol'] == 'ETH'
        assert response.data[0]['tx_hash'] == get_txs_incoming_tx__less_then_min_value['hash']
        assert response.data[0]['from_address'] == get_txs_incoming_tx__less_then_min_value['from_address']
        assert response.data[0]['to_address'] == ''
        assert response.data[0]['success']
        assert response.data[0]['confirmations'] == get_txs_incoming_tx__less_then_min_value['confirmations']
        assert response.data[0]['block_height'] == get_txs_incoming_tx__less_then_min_value['block']
        assert response.data[0]['date'] == get_txs_incoming_tx__less_then_min_value['date'].isoformat() + 'Z'
