import pytest
from django.urls import reverse
from rest_framework.status import HTTP_200_OK, HTTP_404_NOT_FOUND
from rest_framework.test import APIClient

from exchange.explorer.blocks.models import GetBlockStats
from exchange.explorer.blocks.tests.fixtures.block_head_fixture import (
    eth_get_block_stats,
    eth_get_block_stats__with_min_available_block_less_than_after_block_number,
    eth_get_block_stats__with_null_min_available_block,
)
from exchange.explorer.blocks.tests.fixtures.block_info_fixture import (
    AFTER_BLOCK_NUMBER,
    TO_BLOCK_NUMBER,
    btc_transfer__inside_block_range,
    eth_transfer__block_height_gt_before_block_number,
    eth_transfer__block_number_equals_to_after_block_number,
    eth_transfer__block_number_equals_to_before_block_number,
)
from exchange.explorer.networkproviders.models import Network
from exchange.explorer.networkproviders.tests.fixtures.network_fixture import btc_network, eth_network
from exchange.explorer.transactions.models import Transfer

pytestmark = pytest.mark.django_db


def test__get_block_info__when_network_not_exist__returns_404(client: APIClient):
    url = reverse('blocks:block_info', kwargs={'network': 'NOT_EXIST'})

    response = client.get(url, data={
        'after_block_number': AFTER_BLOCK_NUMBER,
        'to_block_number': TO_BLOCK_NUMBER,
    })

    assert response.status_code == HTTP_404_NOT_FOUND


def test__get_block_info__when_min_available_block_null__returns_404(
        client: APIClient,
        eth_network: Network,
        eth_get_block_stats__with_null_min_available_block: GetBlockStats):
    url = reverse('blocks:block_info', kwargs={'network': eth_network.name})

    response = client.get(url, data={
        'after_block_number': AFTER_BLOCK_NUMBER,
        'to_block_number': TO_BLOCK_NUMBER,
    })

    assert response.status_code == HTTP_404_NOT_FOUND


def test__get_block_info__when_after_block_number_less_than_min_available_block__returns_404(
        client: APIClient,
        eth_network: Network,
        eth_get_block_stats__with_min_available_block_less_than_after_block_number: GetBlockStats
):
    url = reverse('blocks:block_info', kwargs={'network': eth_network.name})

    response = client.get(url, data={
        'after_block_number': AFTER_BLOCK_NUMBER,
        'to_block_number': TO_BLOCK_NUMBER,
    })

    assert response.status_code == HTTP_404_NOT_FOUND


def test__get_block_info__when_transfer_block_height_equals_to_after_block_number__returns_200_with_transaction(
        client: APIClient,
        eth_network: Network,
        eth_get_block_stats: GetBlockStats,
        eth_transfer__block_number_equals_to_after_block_number: Transfer
):
    url = reverse('blocks:block_info', kwargs={'network': eth_network.name})

    response = client.get(url, data={
        'after_block_number': AFTER_BLOCK_NUMBER,
        'to_block_number': TO_BLOCK_NUMBER,
    })

    assert response.status_code == HTTP_200_OK
    assert len(response.json().get('transactions')) == 1

    transaction = response.json().get('transactions')[0]
    assert transaction['tx_hash'] == eth_transfer__block_number_equals_to_after_block_number.tx_hash
    assert transaction['success'] == eth_transfer__block_number_equals_to_after_block_number.success
    assert transaction['from_address'] == eth_transfer__block_number_equals_to_after_block_number.from_address_str
    assert transaction['to_address'] == eth_transfer__block_number_equals_to_after_block_number.to_address_str
    assert transaction['value'] == eth_transfer__block_number_equals_to_after_block_number.value
    assert transaction['symbol'] == eth_transfer__block_number_equals_to_after_block_number.symbol
    assert transaction['block_height'] == eth_transfer__block_number_equals_to_after_block_number.block_height


def test__get_block_info__when_transfer_block_height_equals_to_before_block_number__returns_200(
        client: APIClient,
        eth_network: Network,
        eth_get_block_stats: GetBlockStats,
        eth_transfer__block_number_equals_to_before_block_number: Transfer
):
    url = reverse('blocks:block_info', kwargs={'network': eth_network.name})

    response = client.get(url, data={
        'after_block_number': AFTER_BLOCK_NUMBER,
        'to_block_number': TO_BLOCK_NUMBER,
    })

    assert response.status_code == HTTP_200_OK
    assert len(response.json().get('transactions')) == 1

    transaction = response.json().get('transactions')[0]

    assert transaction['tx_hash'] == eth_transfer__block_number_equals_to_before_block_number.tx_hash
    assert transaction['success'] == eth_transfer__block_number_equals_to_before_block_number.success
    assert transaction['from_address'] == eth_transfer__block_number_equals_to_before_block_number.from_address_str
    assert transaction['to_address'] == eth_transfer__block_number_equals_to_before_block_number.to_address_str
    assert transaction['value'] == eth_transfer__block_number_equals_to_before_block_number.value
    assert transaction['symbol'] == eth_transfer__block_number_equals_to_before_block_number.symbol
    assert transaction['block_height'] == eth_transfer__block_number_equals_to_before_block_number.block_height


def test__get_block_info__when_block_height_gt_before_block_number__returns_200_with_no_transactions(
        client: APIClient,
        eth_network: Network,
        eth_get_block_stats: GetBlockStats,
        eth_transfer__block_height_gt_before_block_number: Transfer
):
    url = reverse('blocks:block_info', kwargs={'network': eth_network.name})

    response = client.get(url, data={
        'after_block_number': AFTER_BLOCK_NUMBER,
        'to_block_number': TO_BLOCK_NUMBER,
    })

    assert response.status_code == HTTP_200_OK
    assert response.json().get('transactions') == []


def test__get_block_info__when_another_network_transfer_exists__returns_200_with_no_transactions(
        client: APIClient,
        eth_network: Network,
        btc_network: Network,
        eth_get_block_stats: GetBlockStats,
        btc_transfer__inside_block_range: Transfer
):
    url = reverse('blocks:block_info', kwargs={'network': eth_network.name})

    response = client.get(url, data={
        'after_block_number': AFTER_BLOCK_NUMBER,
        'to_block_number': TO_BLOCK_NUMBER,
    })

    assert response.status_code == HTTP_200_OK
    assert response.json().get('transactions') == []
