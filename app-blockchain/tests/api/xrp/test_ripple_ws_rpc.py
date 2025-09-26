import pytest

from exchange.blockchain.api.xrp.new_xrp_rpc import RippleWsApi
from exchange.blockchain.tests.api.xrp.test_xrp_rpc import TestRippleRpcClusterApiFromExplorer, \
    RippleRpcClusterApiCalls


@pytest.mark.slow
class TestRippleRpcS1ApiCalls(RippleRpcClusterApiCalls):
    api = RippleWsApi.get_instance()


class TestRippleRpcS1FromExplorer(TestRippleRpcClusterApiFromExplorer):
    api = RippleWsApi
