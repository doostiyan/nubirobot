import pytest
from django.urls import reverse
from rest_framework.status import HTTP_200_OK
from rest_framework.test import APIClient

from exchange.explorer.blocks.models import GetBlockStats
from exchange.explorer.networkproviders.models import Network
from exchange.explorer.networkproviders.tests.fixtures.network_fixture import eth_network

from .fixtures.block_head_fixture import eth_get_block_stats
from .fixtures.block_info_fixture import AFTER_BLOCK_NUMBER

pytestmark = pytest.mark.django_db


def test__get_block_head__returns_successful(
        client: APIClient,
        eth_get_block_stats: GetBlockStats,
        eth_network: Network):
    url = reverse('blocks:block_head', kwargs={'network': eth_network.name})

    response = client.get(url)

    assert response.status_code == HTTP_200_OK
    assert response.json().get('block_head') == AFTER_BLOCK_NUMBER
