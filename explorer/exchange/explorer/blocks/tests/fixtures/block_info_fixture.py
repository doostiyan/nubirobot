from datetime import datetime

import pytest

from exchange.explorer.networkproviders.models import Network, Operation
from exchange.explorer.transactions.models import Transfer

AFTER_BLOCK_NUMBER = 12
TO_BLOCK_NUMBER = 120


@pytest.fixture
def eth_transfer__block_number_equals_to_after_block_number(eth_network: Network) -> Transfer:
    return Transfer.objects.create(
        tx_hash='random hash1',
        from_address_str='from1',
        to_address_str='to1',
        success=True,
        value='12.121',
        symbol='ETH',
        source_operation=Operation.BLOCK_TXS,
        created_at=datetime.now(),
        network=eth_network,
        block_height=AFTER_BLOCK_NUMBER)


@pytest.fixture
def eth_transfer__block_number_equals_to_before_block_number(eth_network: Network) -> Transfer:
    return Transfer.objects.create(
        tx_hash='random hash2',
        from_address_str='from2',
        to_address_str='to2',
        success=True,
        value='12.122',
        symbol='ETH',
        source_operation=Operation.BLOCK_TXS,
        created_at=datetime.now(),
        network=eth_network,
        block_height=TO_BLOCK_NUMBER)


@pytest.fixture
def eth_transfer__block_height_gt_before_block_number(eth_network: Network) -> Transfer:
    return Transfer.objects.create(
        tx_hash='random hash3',
        from_address_str='from3',
        to_address_str='to3',
        success=True,
        value='12.123',
        symbol='ETH',
        source_operation=Operation.BLOCK_TXS,
        created_at=datetime.now(),
        network=eth_network,
        block_height=TO_BLOCK_NUMBER + 1)


@pytest.fixture
def btc_transfer__inside_block_range(btc_network: Network) -> Transfer:
    return Transfer.objects.create(
        tx_hash='random hash4',
        from_address_str='from4',
        to_address_str='to4',
        success=True,
        value='12.124',
        symbol='BTC',
        source_operation=Operation.BLOCK_TXS,
        created_at=datetime.now(),
        network=btc_network,
        block_height=TO_BLOCK_NUMBER - 1)
