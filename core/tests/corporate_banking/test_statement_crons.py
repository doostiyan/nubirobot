import datetime
from unittest.mock import MagicMock, patch

from django.test import TestCase

from exchange.base.calendar import ir_now
from exchange.corporate_banking.crons import GetDailyStatementsCron, GetStatementsCron


class TestGetStatementsCron(TestCase):
    @patch('exchange.corporate_banking.crons.Banker.get_statements')
    @patch('exchange.corporate_banking.crons.report_exception')
    def test_run_successful(self, mock_report_exception, mock_get_statements):
        cron = GetStatementsCron()
        cron.last_successful_start = ir_now() - datetime.timedelta(minutes=15)
        cron.run()

        assert mock_get_statements.call_count == len(cron.providers)
        mock_report_exception.assert_not_called()

    @patch('exchange.corporate_banking.crons.Banker.get_statements', side_effect=Exception('Test Exception'))
    @patch('exchange.corporate_banking.crons.report_exception')
    def test_run_exception_handling(self, mock_report_exception, mock_get_statements):
        cron = GetStatementsCron()
        cron.last_successful_start = ir_now() - datetime.timedelta(minutes=15)

        cron.run()

        assert mock_get_statements.call_count == len(cron.providers)
        mock_report_exception.assert_called()


class TestGetDailyStatementsCron(TestCase):
    @patch('exchange.corporate_banking.crons.Banker.get_statements')
    @patch('exchange.corporate_banking.models.ThirdpartyLog.objects.filter')
    def test_run_successful(self, mock_filter, mock_get_statements):
        mock_filter.return_value.delete = MagicMock()
        cron = GetDailyStatementsCron()
        cron.run()

        assert mock_get_statements.call_count == len(cron.providers)
        mock_filter.assert_called()
        mock_filter.return_value.delete.assert_called()

    @patch('exchange.corporate_banking.crons.Banker.get_statements', side_effect=Exception('Test Exception'))
    @patch('exchange.corporate_banking.crons.report_exception')
    def test_run_exception_handling(self, mock_report_exception, mock_get_statements):
        cron = GetDailyStatementsCron()

        cron.run()

        assert mock_get_statements.call_count == len(cron.providers)
        mock_report_exception.assert_called()
