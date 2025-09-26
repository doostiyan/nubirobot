import pytest

from tests.matcher.data_tester import DataTester


@pytest.mark.matcher
class MarketSell(DataTester):

    test_category = 'market_sell'

    def test_unexpected_price(self):
        self.run_test(self.test_category, 'unexpected_price')

    def test_over_priced_market_sell(self):
        self.run_test(self.test_category, 'over_priced_market')

    def test_under_priced_market_sell(self):
        self.run_test(self.test_category, 'under_priced_market')

    def test_margin_match(self):
        self.run_test(self.test_category, 'margin_match')

    def test_all_market(self):
        self.run_test(self.test_category, 'all_market')
