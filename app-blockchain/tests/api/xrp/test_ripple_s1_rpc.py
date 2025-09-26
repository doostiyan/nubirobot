import pytest

from exchange.blockchain.api.xrp.new_xrp_rpc import RippleS1Api
from exchange.blockchain.tests.api.xrp.test_xrp_rpc import TestRippleRpcClusterApiFromExplorer, \
    RippleRpcClusterApiCalls


@pytest.mark.slow
class TestRippleRpcS1ApiCalls(RippleRpcClusterApiCalls):
    api = RippleS1Api.get_instance()


class TestRippleRpcS1FromExplorer(TestRippleRpcClusterApiFromExplorer):
    api = RippleS1Api
