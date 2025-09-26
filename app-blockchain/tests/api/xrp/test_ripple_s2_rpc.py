import pytest

from exchange.blockchain.api.xrp.new_xrp_rpc import RippleS2Api
from exchange.blockchain.tests.api.xrp.test_xrp_rpc import TestRippleRpcClusterApiFromExplorer, \
    RippleRpcClusterApiCalls


@pytest.mark.slow
class TestRippleRpcS1ApiCalls(RippleRpcClusterApiCalls):
    api = RippleS2Api.get_instance()


class TestRippleRpcS1FromExplorer(TestRippleRpcClusterApiFromExplorer):
    api = RippleS2Api
