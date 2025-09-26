import pytest

from tests.matcher.data_tester import DataTester


@pytest.mark.matcher
class SimpleUnderPricedSell(DataTester):

    test_category = 'under_priced_sell'
    test_name = 'simple_under_priced_sell'

    def test_simple_under_priced_sell(self):
        self.run_test()
