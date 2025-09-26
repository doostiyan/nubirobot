from datetime import datetime, timezone
from unittest.mock import patch, call

from django.test import TestCase

from exchange.base.calendar import ir_tz
from exchange.corporate_banking.models import ACCOUNT_TP, COBANK_PROVIDER, NOBITEX_BANK_CHOICES, CoBankAccount
from exchange.corporate_banking.services.banker import Banker
from exchange.corporate_banking.tasks import rerun_get_statement_for_period_task


class RerunGetStatementForPeriodTaskTest(TestCase):
    def setUp(self):
        self.cobank_account = CoBankAccount.objects.create(
            provider=COBANK_PROVIDER.toman,
            provider_bank_id=4,
            bank=NOBITEX_BANK_CHOICES.saderat,
            iban='IR999999999999999999999992',
            account_number='OPER-1234',
            account_tp=ACCOUNT_TP.operational,
        )

    @patch('exchange.corporate_banking.tasks.Banker.__init__', return_value=None)
    @patch('exchange.corporate_banking.tasks.Banker.get_bank_statements')
    @patch('exchange.corporate_banking.tasks.Banker.get_statements')
    def test_banker_get_statements_called_correctly(
        self, get_statements_mock, get_bank_statements_mock, mock_banker_init
    ):
        from_time = datetime(year=2000, month=2, day=20, hour=20, minute=2, second=2, tzinfo=ir_tz())
        to_time = datetime(year=2000, month=2, day=20, hour=20, minute=5, second=5, tzinfo=ir_tz())
        rerun_get_statement_for_period_task(from_time.isoformat(), to_time.isoformat())
        assert get_statements_mock.call_count == 2
        get_bank_statements_mock.assert_not_called()
        mock_banker_init.assert_has_calls(
            [
                call(COBANK_PROVIDER.toman, from_time, to_time),
                call(COBANK_PROVIDER.jibit, from_time, to_time),
            ],
            any_order=True,
        )

        get_statements_mock.reset_mock()
        from_time = datetime(year=2000, month=2, day=20, hour=20, minute=2, second=2, tzinfo=timezone.utc)
        to_time = datetime(year=2000, month=2, day=20, hour=20, minute=5, second=5, tzinfo=timezone.utc)
        rerun_get_statement_for_period_task(from_time.isoformat(), to_time.isoformat())
        assert get_statements_mock.call_count == 2
        get_bank_statements_mock.assert_not_called()

    @patch('exchange.corporate_banking.tasks.Banker.get_bank_statements')
    @patch('exchange.corporate_banking.tasks.Banker.get_statements')
    def test_banker_get_bank_statements_called_correctly(self, get_statements_mock, get_bank_statements_mock):
        from_time = datetime(year=2000, month=2, day=20, hour=20, minute=2, second=2, tzinfo=ir_tz())
        to_time = datetime(year=2000, month=2, day=20, hour=20, minute=5, second=5, tzinfo=ir_tz())
        rerun_get_statement_for_period_task(from_time.isoformat(), to_time.isoformat(), self.cobank_account.pk)
        get_statements_mock.assert_not_called()
        get_bank_statements_mock.assert_called_once_with(self.cobank_account)

        get_bank_statements_mock.reset_mock()
        from_time = datetime(year=2000, month=2, day=20, hour=20, minute=2, second=2, tzinfo=timezone.utc)
        to_time = datetime(year=2000, month=2, day=20, hour=20, minute=5, second=5, tzinfo=timezone.utc)
        rerun_get_statement_for_period_task(from_time.isoformat(), to_time.isoformat(), self.cobank_account.pk)
        get_statements_mock.assert_not_called()
        get_bank_statements_mock.assert_called_once_with(self.cobank_account)

    @patch('exchange.corporate_banking.tasks.Banker.get_bank_statements')
    @patch('exchange.corporate_banking.tasks.Banker.get_statements')
    @patch('exchange.corporate_banking.tasks.rerun_get_statement_for_period_task')
    def test_banker_get_statements_banker_initiated_correctly(
        self,
        rerun_task_mock,
        get_statements_mock,
        get_bank_statements_mock,
    ):
        def mock_rerun_task(from_time: str, to_time: str, cobank_account_pk: int = None):
            from_time = datetime.fromisoformat(from_time).astimezone(ir_tz())
            to_time = datetime.fromisoformat(to_time).astimezone(ir_tz())
            account = None
            if cobank_account_pk:
                account = CoBankAccount.objects.filter(pk=cobank_account_pk).first()
            if account:
                banker = Banker(account.provider, from_time, to_time)
                banker.get_bank_statements(account)
            else:
                banker = Banker(COBANK_PROVIDER.toman, from_time, to_time)
                banker.get_statements()
            return banker

        rerun_task_mock.side_effect = mock_rerun_task

        from_time = datetime(year=2000, month=2, day=20, hour=20, minute=2, second=2, tzinfo=ir_tz())
        to_time = datetime(year=2000, month=2, day=20, hour=20, minute=5, second=5, tzinfo=ir_tz())
        banker = rerun_task_mock(from_time.isoformat(), to_time.isoformat())
        assert banker.from_time == from_time
        assert banker.to_time == to_time

        from_time = datetime(year=2000, month=2, day=20, hour=20, minute=2, second=2, tzinfo=timezone.utc)
        to_time = datetime(year=2000, month=2, day=20, hour=20, minute=5, second=5, tzinfo=timezone.utc)
        banker = rerun_task_mock(from_time.isoformat(), to_time.isoformat(), self.cobank_account.pk)
        assert banker.from_time == from_time
        assert banker.to_time == to_time

    @patch('exchange.corporate_banking.tasks.Banker.get_bank_statements')
    @patch('exchange.corporate_banking.tasks.Banker.get_statements')
    def test_banker_get_statements_with_specific_provider(self, get_statements_mock, get_bank_statements_mock):
        from_time = datetime(year=2000, month=2, day=20, hour=20, minute=2, second=2, tzinfo=ir_tz())
        to_time = datetime(year=2000, month=2, day=20, hour=20, minute=5, second=5, tzinfo=ir_tz())
        rerun_get_statement_for_period_task(from_time.isoformat(), to_time.isoformat(), provider=COBANK_PROVIDER.toman)
        get_statements_mock.assert_called_once()
        get_bank_statements_mock.assert_not_called()
