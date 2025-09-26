import pytest

from exchange.blockchain.api.arbitrum.ankr_arbitrum import AnkrArbitrumApi
from exchange.blockchain.tests.api.arbitrum.test_alchemy_arbitrum import TestAlchemyArbitrumApiCalls, \
    TestAlchemyArbitrumFromExplorer

@pytest.mark.slow
class TestAnkrArbitrumApiCalls(TestAlchemyArbitrumApiCalls):
    api = AnkrArbitrumApi.get_instance()


class TestAnkrArbitrumFromExplorer(TestAlchemyArbitrumFromExplorer):
    api = AnkrArbitrumApi
