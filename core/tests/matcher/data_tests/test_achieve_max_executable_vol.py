import pytest

from tests.matcher.data_tester import DataTester


@pytest.mark.matcher
class AchieveMaxExecutableVolume(DataTester):
    # https://academy.binance.com/en/articles/deep-dive-into-the-binance-dex-match-engine

    test_category = 'achieve_max_executable_volume'
    test_name = 'max_executable_volume'

    def test_max_executable_volume(self):
        self.run_test()
