import pytest

from tests.matcher.data_tester import DataTester


@pytest.mark.matcher
class MarketBuy(DataTester):

    test_category = 'market_buy'

    def test_under_priced_buy(self):
        self.run_test(self.test_category, 'under_priced_buy')

    def test_over_test(self):
        self.run_test(self.test_category, 'over_test')

    def test_over_priced_buy(self):
        self.run_test(self.test_category, 'over_priced_buy')
