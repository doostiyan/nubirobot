import pytest

from tests.matcher.data_tester import DataTester


@pytest.mark.matcher
class SimpleUnderPricedBuy(DataTester):

    test_category = 'no_match'
    test_name = 'under_priced_buy'

    def test_simple_under_priced_buy(self):
        self.run_test()


@pytest.mark.matcher
class SimpleOverPricedSell(DataTester):

    test_category = 'no_match'
    test_name = 'over_priced_sell'

    def test_simple_over_priced_sell(self):
        self.run_test()
