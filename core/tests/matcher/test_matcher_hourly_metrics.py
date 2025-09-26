from django.test import TestCase

from exchange.matcher.timer import MatcherHourlyMetrics


class TestMatcherHourlyMetrics(TestCase):
    def setUp(self):
        MatcherHourlyMetrics.reset_metrics()

    def test_get_report_message(self):
        MatcherHourlyMetrics.update_round_times("getOrders", 0.6)
        MatcherHourlyMetrics.update_metrics(trades_count=27, tps=45, markets='10')
        MatcherHourlyMetrics.update_round_times("getOrders", 0.9)
        MatcherHourlyMetrics.update_metrics(trades_count=9, tps=10, markets='23')
        MatcherHourlyMetrics.update_round_times("commitTrade", 120)
        MatcherHourlyMetrics.update_metrics(trades_count=510, tps=4.25, markets='48')
        MatcherHourlyMetrics.update_round_times("TradeTransactions", 15)
        MatcherHourlyMetrics.update_metrics(trades_count=50, tps=16, markets='2')

        expected_total_trades = 596
        expected_total_runs = 4
        expected_max_tps = 45

        message = MatcherHourlyMetrics.get_report()

        assert f'Trades:{expected_total_trades:,}' in message
        assert f'Runs:{expected_total_runs:,}' in message
        assert f'MaxT:{expected_max_tps}' in message
        assert f'SLA: {"/".join(MatcherHourlyMetrics.SLA_CUTOFFS.keys())}' in message
        assert 'Runs: 0/2/0/1/1/0' in message
        assert 'MaxTPS: 0/45/0/16/4.25/0' in message
        assert 'Markets: -/10/-/2/48/-' in message
        assert 'LongestStep: -/getOrders/-/TradeTransactions/commitTrade/-' in message
