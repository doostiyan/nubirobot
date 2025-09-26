import pytest

from exchange.explorer.blocks.models import GetBlockStats
from exchange.explorer.networkproviders.models import Network

from .block_info_fixture import AFTER_BLOCK_NUMBER


@pytest.fixture
def eth_get_block_stats(eth_network: Network) -> GetBlockStats:
    return GetBlockStats.objects.create(network=eth_network,
                                        min_available_block=AFTER_BLOCK_NUMBER,
                                        latest_processed_block=AFTER_BLOCK_NUMBER)


@pytest.fixture
def eth_get_block_stats__with_null_min_available_block(eth_network: Network) -> GetBlockStats:
    return GetBlockStats.objects.create(network=eth_network,
                                        latest_processed_block=AFTER_BLOCK_NUMBER)


@pytest.fixture
def eth_get_block_stats__with_min_available_block_less_than_after_block_number(eth_network: Network) -> GetBlockStats:
    return GetBlockStats.objects.create(network=eth_network,
                                        latest_processed_block=AFTER_BLOCK_NUMBER - 10)
