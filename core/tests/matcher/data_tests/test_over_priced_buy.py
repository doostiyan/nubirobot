import pytest

from tests.matcher.data_tester import DataTester


@pytest.mark.matcher
class SimpleOverPricedBuy(DataTester):

    test_category = 'over_priced_buy'
    test_name = 'simple_over_priced_buy'

    def test_simple_over_priced_buy(self):
        self.run_test()
