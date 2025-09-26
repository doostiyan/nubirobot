from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import override_settings

from tests.matcher.test_matcher import BaseTestMatcher


@pytest.mark.interactive
@pytest.mark.matcher
@pytest.mark.matcherFull
@override_settings(ASYNC_TRADE_COMMIT=True)
@patch('exchange.matcher.matcher.MARKET_ORDER_MAX_PRICE_DIFF', Decimal('0.01'))
class TestMatcherHeavily(BaseTestMatcher):
    """
    Run a round of matcher with over 200 pending trades to compare matcher step timings.

    Sample result:
        UNKNOWNUSDT  S:207  B:221
        ...
        REPORT {'matches': 279, 'failures': 0, 'skipped': 80}
        TradeTransactions:1057ms/30%  BlockedBalances:929ms/26%  CommitTrade:708ms/20%
        GetWallets:428ms/12%  CreateTrade:283ms/8%  MatchFees:105ms/3%
        Markets:1 …
    """

    root = 'tests/matcher/test_cases/performance'
    USER_SIZE = 200

    def setUp(self):
        self.timing_enabled_patch = patch('exchange.matcher.timer.ENV_TIMING_ENABLED', True)
        self.timing_enabled_patch.start()

    def tearDown(self):
        self.timing_enabled_patch.stop()
