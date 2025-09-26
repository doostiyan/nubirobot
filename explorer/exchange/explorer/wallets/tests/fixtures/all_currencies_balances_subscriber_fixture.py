import pytest
from unittest.mock import Mock
from exchange.explorer.basis.tests.fixtures.message_broker_fixture import message_broker
from exchange.explorer.wallets.subscribers.all_currencies_balances_request_subscriber import AllCurrenciesBalancesRequestSubscriber
from exchange.blockchain.api.general.dtos.dtos import NewBalancesV2

@pytest.fixture
def subscriber(message_broker):
    return AllCurrenciesBalancesRequestSubscriber(message_broker)

@pytest.fixture
def batch_request_data():
    return {
        "network": "ethereum",
        "addresses": ["0x123", "0x456"]
    }

@pytest.fixture
def batch_balances_result():
    return [
        NewBalancesV2(
            address="0x123",
            balance="1.0",
            contract_address="0x0000000000000000000000000000000000000000",
            symbol="ETH",
            network="ethereum",
            block_number=16027518,
            block_timestamp="2025-03-26T05:56:30+00:00"
        ),
        NewBalancesV2(
            address="0x456",
            balance="2.0",
            contract_address="0x0000000000000000000000000000000000000000",
            symbol="ETH",
            network="ethereum",
            block_number=16027518,
            block_timestamp="2025-03-26T05:56:30+00:00"
        )
    ] 