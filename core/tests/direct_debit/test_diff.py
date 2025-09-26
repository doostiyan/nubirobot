import decimal
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import responses
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status

from exchange.accounts.models import User
from exchange.base.models import Settings
from exchange.direct_debit.models import DailyDirectDeposit, DirectDeposit
from exchange.report.crons import SaveDailyDirectDeposits
from tests.direct_debit.constants import (
    sample_faraboom_response,
    sample_faraboom_response_kesh,
    sample_faraboom_response_mehr,
    sample_faraboom_response_tej,
)
from tests.direct_debit.helper import DirectDebitMixins, MockResponse


class DirectDepositDiffTest(TestCase, DirectDebitMixins):
    def setUp(self):
        self.user = User.objects.get(pk=202)
        self.bank = self.create_bank(bank_id='MELIIR')
        self.contract = self.create_contract(user=self.user, bank=self.bank)
        self.succeed_direct_debit = self.create_deposit(
            user=self.user,
            contract=self.contract,
            amount=decimal.Decimal('1000000'),
            trace_id='7004fc819218449bb496c07730f572fa',
            reference_id='00001713265274211422',
        )

        self.failed_direct_debit = self.create_deposit(
            user=self.user,
            contract=self.contract,
            amount=decimal.Decimal('1000'),
            trace_id='775dc5fe95db4bc4856f5ccec6b48fb8',
            status=DirectDeposit.STATUS.failed,
            reference_id='',
        )
        self.api_url = f'{self.base_url}/v1/reports/transactions'
        cache.set('direct_debit_access_token', 'test_direct_debit_access_token')
        Settings.set_cached_json('direct_deposit_skip_banks_sync', [])

    def mock_responses(self, start_date, end_date):
        self.mock_response(sample_faraboom_response_tej, start_date, end_date, 'BTEJIR')
        self.mock_response([], start_date, end_date, 'MELIIR')
        self.mock_response(sample_faraboom_response_mehr, start_date, end_date, 'MEHRIR')
        self.mock_response(sample_faraboom_response_kesh, start_date, end_date, 'KESHIR')

    def mock_response(self, faraboom_response, start_date, end_date, bank_code):
        responses.post(
            url=self.api_url,
            json=faraboom_response,
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'offset': 0,
                        'length': 100,
                        'start_date': start_date,
                        'end_date': end_date,
                        'bank_code': bank_code,
                    },
                ),
            ],
        )

    @patch('exchange.direct_debit.integrations.faraboom.FaraboomClient.request')
    def test_cron_job(self, mock_fetch_deposit_response):
        mock_fetch_deposit_response.return_value = MockResponse(sample_faraboom_response, status.HTTP_200_OK)
        SaveDailyDirectDeposits().run()
        saved_deposits = DailyDirectDeposit.objects.all()
        assert len(saved_deposits) == 19
        succeed_daily_direct_debit = DailyDirectDeposit.objects.get(trace_id=self.succeed_direct_debit.trace_id)
        assert succeed_daily_direct_debit.transaction_amount == self.succeed_direct_debit.amount
        assert succeed_daily_direct_debit.status == DailyDirectDeposit.STATUS.succeed
        assert succeed_daily_direct_debit.reference_id == self.succeed_direct_debit.reference_id
        assert succeed_daily_direct_debit.deposit == self.succeed_direct_debit
        failed_daily_deposit = DailyDirectDeposit.objects.get(trace_id=self.failed_direct_debit.trace_id)
        assert failed_daily_deposit.transaction_amount == self.failed_direct_debit.amount
        assert failed_daily_deposit.status == DailyDirectDeposit.STATUS.failed
        assert failed_daily_deposit.reference_id == self.failed_direct_debit.reference_id
        assert failed_daily_deposit.deposit == self.failed_direct_debit

    @responses.activate
    @patch('exchange.report.crons.ir_now', return_value=datetime(year=2024, month=3, day=15, tzinfo=timezone.utc))
    def test_cron_job_with_bank_code(self, _):
        self.create_bank(bank_id='BTEJIR')
        self.mock_responses('2024-02-29T21:00:00.000Z', '2024-03-15T03:20:00.000Z')
        SaveDailyDirectDeposits().run()
        saved_deposits = DailyDirectDeposit.objects.all()
        assert len(saved_deposits) == 2

        assert Settings.get('daily_direct_debit_sentinel_v4') == '2024-03-14T23:50:00+00:00'

        self.create_bank(bank_id='MEHRIR')
        self.mock_responses(
            '2024-03-15T00:20:00.000Z',
            '2024-03-15T03:20:00.000Z',
        )
        SaveDailyDirectDeposits().run()
        saved_deposits = DailyDirectDeposit.objects.all()
        assert len(saved_deposits) == 5

        self.create_bank(bank_id='KESHIR')
        SaveDailyDirectDeposits().run()
        saved_deposits = DailyDirectDeposit.objects.all()
        assert len(saved_deposits) == 7

    @patch('exchange.direct_debit.integrations.faraboom.FaraboomClient.request')
    @patch('exchange.report.crons.ir_now', return_value=datetime(year=2024, month=3, day=15, tzinfo=timezone.utc))
    def test_sentinel_date_update(self, _, mock_fetch_deposit_response):
        mock_fetch_deposit_response.return_value = MockResponse(sample_faraboom_response, status.HTTP_200_OK)
        with patch('exchange.report.crons.Settings.set_datetime') as mock_set_datetime:
            SaveDailyDirectDeposits().run()
            expected_to_date = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc) - timedelta(minutes=10)
            mock_set_datetime.assert_called_once_with('daily_direct_debit_sentinel_v4', expected_to_date)

    @patch('exchange.direct_debit.integrations.faraboom.FaraboomClient.request')
    def test_insufficient_balance(self, mock_fetch_deposit_response):
        failed_response = sample_faraboom_response[2]
        failed_response['error_type'] = 'BALANCE_FAILED'
        mock_fetch_deposit_response.return_value = MockResponse(
            [
                failed_response,
            ],
            status.HTTP_200_OK,
        )
        SaveDailyDirectDeposits().run()
        saved_deposits = DailyDirectDeposit.objects.all()
        assert len(saved_deposits) == 1
        failed_daily_direct_debit = DailyDirectDeposit.objects.get(trace_id=self.failed_direct_debit.trace_id)
        assert failed_daily_direct_debit.status == DailyDirectDeposit.STATUS.insufficient_balance
