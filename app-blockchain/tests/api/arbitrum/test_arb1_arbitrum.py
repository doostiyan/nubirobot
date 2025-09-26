import pytest

from exchange.blockchain.api.arbitrum.arb1_arbitrum import Arb1ArbitrumApi
from exchange.blockchain.tests.api.arbitrum.test_alchemy_arbitrum import TestAlchemyArbitrumApiCalls, \
    TestAlchemyArbitrumFromExplorer


@pytest.mark.slow
class TestAnkrArbitrumApiCalls(TestAlchemyArbitrumApiCalls):
    api = Arb1ArbitrumApi.get_instance()


class TestArb1ArbitrumFromExplorer(TestAlchemyArbitrumFromExplorer):
    api = Arb1ArbitrumApi
