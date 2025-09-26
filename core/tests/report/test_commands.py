import pytest
from django.core.management import call_command
from django.test import TestCase
from unittest.mock import patch

from django.utils import timezone
from requests import HTTPError

from exchange.accounts.models import BankAccount
from exchange.base.models import RIAL
from exchange.report.models import DailyShetabDeposit, DailyWithdraw
from exchange.shetab.models import ShetabDeposit
from exchange.wallet.models import WithdrawRequest, Wallet


class FetchJibitHistoryCommandTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.deposit = ShetabDeposit.objects.create(
            pk=123, broker=ShetabDeposit.BROKER.jibit_v2, user_id=201, amount=100000,
        )
        bank_account = BankAccount.get_generic_system_account()
        wallet = Wallet.get_user_wallet(bank_account.user, RIAL)
        cls.withdraw = WithdrawRequest.objects.create(pk=123, wallet=wallet, target_account=bank_account, amount=100000)

    @staticmethod
    def get_successful_jibit_v1_purchase_response(count=1, offset=0):
        today = timezone.now().date()
        return {
            'pageNumber': 1,
            'size': 20,
            'numberOfElements': count,
            'hasNext': count >= 20,
            'hasPrevious': offset > 0,
            'elements': [{
                'id': f'r6oaJgZ{i}',
                'amount': 100000.0,
                'currency': 'RIALS',
                'callbackUrl': 'https://www.client.ir/purchases/123456789/callback',
                'status': 'IN_PROGRESS',
                'referenceNumber': f'nobitex{120 + i}',
                'expirationDate': '2022-02-01T10:17:41.095731Z',
                'userIdentifier': '201',
                'payerCard': '434567-3452',
                'nationalCode': '4060145796',
                'description': f'nobitex{120 + i}',
                'initPayerIp': '43.23.6.28',
                'redirectPayerIp': '45.73.6.28',
                'createdAt': f'{today}T10:09:21.095721Z',
                'modifiedAt': f'{today}T10:12:41.095732Z',
                **({
                    'additionalData': {
                        'someTag': 'some-value'
                    },
                } if i % 2 else {})
            } for i in range(offset, offset + count)]
        }

    @staticmethod
    def get_successful_jibit_v2_purchase_response(count=1, offset=0):
        today = timezone.now().date()
        return {
            'pageNumber': 1,
            'size': 20,
            'numberOfElements': count,
            'hasNext': count >= 20,
            'hasPrevious': offset > 0,
            'elements': [{
                'purchaseId': 1200 + i,
                'amount': 100000,
                'wage': 5000,
                'fee': 4555,
                'feePaymentType': 'POST_PAID',
                'currency': 'IRR',
                'wltBalance': 100000,
                'feeBalance': 1111,
                'shwBalance': 3333,
                'callbackUrl': 'https://www.client.ir/purchases/123456789/callback',
                'state': 'READY_TO_VERIFY',
                'clientReferenceNumber': f'nobitex{120 + i}',
                'pspRrn': '84a29cbb205c4aa18dc71b8e3cb99639',
                'pspReferenceNumber': 'GmshtyjwKSsoD4uz5cpmzY5aBaWxx21mxAYRo92Gx0',
                'pspTraceNumber': 'psp-trace-num',
                'expirationDate': '2022-02-01T10:17:41.095731Z',
                'userIdentifier': '201',
                'payerMobileNumber': '09132517905',
                'payerCardNumber': '434567-3452',
                'payerNationalCode': '4060145796',
                'description': f'nobitex{120 + i}',
                'additionalData': {
                    'someTag': 'some-value'
                },
                'pspMaskedCardNumber': '434567****3452',
                'pspCardOwner': 'Ali Khaksari',
                'pspFailReason': 'UNKNOWN',
                'initPayerIp': '43.23.6.28',
                'redirectPayerIp': '45.73.6.28',
                'pspSettled': False,
                'createdAt': f'{today}T10:09:21.095721Z',
                'billingDate': f'{today}T10:12:41.095732Z',
                'verifiedAt': f'{today}T10:12:11.095728Z',
                'pspSettledAt': f'{today}T10:19:21.095730Z'
            } for i in range(offset, offset + count)]
        }

    @staticmethod
    def get_successful_jibit_v1_transfer_response(count=1, offset=0):
        today = timezone.now().date()
        return {
            'page': 1,
            'size': 10,
            'elements': [{
                'transferID': f'{120 + i}',
                'transferMode': 'NORMAL',
                'destination': 'IR000100000000000888888881',
                'destinationFirstName': 'Ali',
                'destinationLastName': 'Khaksari',
                'amount': 99000,
                'currency': 'RIALS',
                'description': f'واریز {120 + i} از نوبیتکس',
                'cancellable': False,
                'state': 'INITIALIZED',
                'createdAt': f'{today}T06:38:23.617287Z',
                'modifiedAt': f'{today}T06:39:12.434124Z',
                **({
                    'bankTransferID': f'{14001119012243308384 + i}'
                } if i % 2 else {
                    'failReason': 'channel.not.found',
                })
            } for i in range(offset, offset + count)] if count else None
        }

    @staticmethod
    def get_successful_jibit_v2_transfer_response(count=1, offset=0):
        today = timezone.now().date()
        return [{
            'transferID': f'{120 + i}',
            'transferMode': 'NORMAL',
            'destination': 'IR000100000000000888888881',
            'destinationFirstName': 'Ali',
            'destinationLastName': 'Khaksari',
            'amount': 99000,
            'currency': 'RIALS',
            'description': f'واریز {120 + i} از نوبیتکس',
            'metadata': {
                'someTag': 'some-value'
            },
            'notifyURL': 'https://www.client.ir/purchases/123456789/notify',
            'cancellable': False,
            'bankTransferID': f'{14001119012243308384 + i}',
            'state': 'IN_PROGRESS',
            'failReason': None,
            'feeCurrency': 'IRR',
            'feeAmount': 10900,
            'createdAt': f'{today}T06:38:23.617287Z',
            'modifiedAt': f'{today}T07:41:26.625254Z',
        } for i in range(offset, offset + count)]

    @patch('exchange.report.crons.SaveDailyDepositsV1.api_func')
    def test_run_for_v1_deposits_fit_in_one_page(self, api_func_mock):
        api_func_mock.return_value = self.get_successful_jibit_v1_purchase_response(count=5)
        assert not DailyShetabDeposit.objects.exists()
        call_command('fetch_jibit_history', api_version=1, mode='deposit')
        assert DailyShetabDeposit.objects.count() == 5
        assert DailyShetabDeposit.objects.filter(deposit=self.deposit).exists()

    @patch('exchange.report.crons.SaveDailyDepositsV1.api_func')
    def test_run_for_v1_deposits_fit_in_multiple_page(self, api_func_mock):
        api_func_mock.side_effect = [
            self.get_successful_jibit_v1_purchase_response(count=20),
            self.get_successful_jibit_v1_purchase_response(count=5, offset=20),
        ]
        assert not DailyShetabDeposit.objects.exists()
        call_command('fetch_jibit_history', api_version=1, mode='deposit')
        assert DailyShetabDeposit.objects.count() == 25
        assert DailyShetabDeposit.objects.filter(deposit=self.deposit).exists()

    @patch('exchange.report.crons.SaveDailyDepositsV1.api_func')
    def test_run_for_v1_deposits_date_filter(self, api_func_mock):
        api_func_mock.side_effect = [self.get_successful_jibit_v1_purchase_response(count=1)]
        assert not DailyShetabDeposit.objects.exists()
        call_command('fetch_jibit_history', api_version=1, mode='deposit', since='2018-11-30', before='2022-08-27')
        assert DailyShetabDeposit.objects.count() == 1
        assert api_func_mock.call_args[0][0].isoformat() == '2018-11-30T00:00:00+04:30'
        assert api_func_mock.call_args[0][1].isoformat() == '2022-08-27T00:00:00+04:30'

    @patch('exchange.report.crons.SaveDailyDepositsV2.api_func')
    def test_run_for_v2_deposits_fit_in_one_page(self, api_func_mock):
        api_func_mock.return_value = self.get_successful_jibit_v2_purchase_response(count=6)
        assert not DailyShetabDeposit.objects.exists()
        call_command('fetch_jibit_history', api_version=2, mode='deposit')
        assert DailyShetabDeposit.objects.count() == 6
        assert DailyShetabDeposit.objects.filter(deposit=self.deposit).exists()

    @patch('exchange.report.crons.SaveDailyDepositsV2.api_func')
    def test_run_for_v2_deposits_fit_in_multiple_page(self, api_func_mock):
        api_func_mock.side_effect = [
            self.get_successful_jibit_v2_purchase_response(count=20),
            self.get_successful_jibit_v2_purchase_response(count=20, offset=20),
            self.get_successful_jibit_v2_purchase_response(count=6, offset=40),
        ]
        assert not DailyShetabDeposit.objects.exists()
        call_command('fetch_jibit_history', api_version=2, mode='deposit')
        assert DailyShetabDeposit.objects.count() == 46
        assert DailyShetabDeposit.objects.filter(deposit=self.deposit).exists()

    @patch('exchange.report.crons.SaveDailyDepositsV2.api_func')
    def test_run_for_v2_deposits_date_filter(self, api_func_mock):
        api_func_mock.side_effect = [self.get_successful_jibit_v2_purchase_response(count=1)]
        assert not DailyShetabDeposit.objects.exists()
        call_command('fetch_jibit_history', api_version=2, mode='deposit', since='2018-11-30', before='2022-08-27')
        assert DailyShetabDeposit.objects.count() == 1
        assert api_func_mock.call_args[0][0].isoformat() == '2018-11-30T00:00:00+04:30'
        assert api_func_mock.call_args[0][1].isoformat() == '2022-08-27T00:00:00+04:30'

    @patch('exchange.report.crons.SaveDailyWithdrawsV1.api_func')
    def test_run_for_v1_withdraws_fit_in_one_page(self, api_func_mock):
        api_func_mock.side_effect = [
            self.get_successful_jibit_v1_transfer_response(count=7),
            self.get_successful_jibit_v1_transfer_response(count=0),
        ]
        assert not DailyWithdraw.objects.exists()
        call_command('fetch_jibit_history', api_version=1, mode='withdraw')
        assert DailyWithdraw.objects.count() == 7
        assert DailyWithdraw.objects.filter(withdraw=self.withdraw).exists()

    @patch('exchange.report.crons.SaveDailyWithdrawsV1.api_func')
    def test_run_for_v1_withdraws_fit_in_multiple_page(self, api_func_mock):
        api_func_mock.side_effect = [
            self.get_successful_jibit_v1_transfer_response(count=10),
            self.get_successful_jibit_v1_transfer_response(count=10, offset=10),
            self.get_successful_jibit_v1_transfer_response(count=10, offset=20),
            self.get_successful_jibit_v1_transfer_response(count=7, offset=30),
            self.get_successful_jibit_v1_transfer_response(count=0),
        ]
        assert not DailyWithdraw.objects.exists()
        call_command('fetch_jibit_history', api_version=1, mode='withdraw')
        assert DailyWithdraw.objects.count() == 37
        assert DailyWithdraw.objects.filter(withdraw=self.withdraw).exists()

    @patch('exchange.report.crons.SaveDailyWithdrawsV1.api_func')
    def test_run_for_v1_withdraws_date_filter(self, api_func_mock):
        api_func_mock.side_effect = [
            self.get_successful_jibit_v1_transfer_response(count=1),
            self.get_successful_jibit_v1_transfer_response(count=0),
        ]
        assert not DailyWithdraw.objects.exists()
        call_command('fetch_jibit_history', api_version=1, mode='withdraw', since='2018-11-30', before='2022-08-27')
        assert DailyWithdraw.objects.count() == 1
        assert api_func_mock.call_args[0][0].isoformat() == '2018-11-30T00:00:00+04:30'
        assert api_func_mock.call_args[0][1].isoformat() == '2022-08-27T00:00:00+04:30'

    @patch('exchange.report.crons.SaveDailyWithdrawsV2.api_func')
    def test_run_for_v2_withdraws_fit_in_one_page(self, api_func_mock):
        api_func_mock.side_effect = [
            self.get_successful_jibit_v2_transfer_response(count=8),
            self.get_successful_jibit_v2_transfer_response(count=0),
        ]
        assert not DailyWithdraw.objects.exists()
        call_command('fetch_jibit_history', api_version=2, mode='withdraw')
        assert DailyWithdraw.objects.count() == 8
        assert DailyWithdraw.objects.filter(withdraw=self.withdraw).exists()

    @patch('exchange.report.crons.SaveDailyWithdrawsV2.api_func')
    def test_run_for_v2_withdraws_fit_in_multiple_page(self, api_func_mock):
        api_func_mock.side_effect = [
            self.get_successful_jibit_v2_transfer_response(count=15),
            self.get_successful_jibit_v2_transfer_response(count=15, offset=15),
            self.get_successful_jibit_v2_transfer_response(count=15, offset=30),
            self.get_successful_jibit_v2_transfer_response(count=8, offset=45),
            self.get_successful_jibit_v2_transfer_response(count=0),
        ]
        assert not DailyWithdraw.objects.exists()
        call_command('fetch_jibit_history', api_version=2, mode='withdraw')
        assert DailyWithdraw.objects.count() == 53
        assert DailyWithdraw.objects.filter(withdraw=self.withdraw).exists()

    @patch('exchange.report.crons.SaveDailyWithdrawsV2.api_func')
    def test_run_for_v2_withdraws_date_filter(self, api_func_mock):
        api_func_mock.side_effect = [
            self.get_successful_jibit_v2_transfer_response(count=1),
            self.get_successful_jibit_v2_transfer_response(count=0),
        ]
        assert not DailyWithdraw.objects.exists()
        call_command('fetch_jibit_history', api_version=2, mode='withdraw', since='2018-11-30', before='2022-08-27')
        assert DailyWithdraw.objects.count() == 1
        assert api_func_mock.call_args[0][0].isoformat() == '2018-11-30T00:00:00+04:30'
        assert api_func_mock.call_args[0][1].isoformat() == '2022-08-27T00:00:00+04:30'

    @patch('exchange.report.crons.SaveDailyDepositsV1.api_func')
    def test_run_for_retry_on_few_consecutive_timeout_error(self, api_func_mock):
        api_func_mock.side_effect = [
            HTTPError(),
            HTTPError(),
            HTTPError(),
            self.get_successful_jibit_v1_purchase_response(count=20),
            HTTPError(),
            HTTPError(),
            self.get_successful_jibit_v1_purchase_response(count=1, offset=20),
        ]
        assert not DailyShetabDeposit.objects.exists()
        call_command('fetch_jibit_history', api_version=1, mode='deposit')
        assert DailyShetabDeposit.objects.count() == 21

    @patch('exchange.report.crons.SaveDailyWithdrawsV2.api_func')
    def test_run_for_fail_on_five_consecutive_timeout_error(self, api_func_mock):
        api_func_mock.side_effect = [
            self.get_successful_jibit_v2_transfer_response(count=1),
            HTTPError(),
            HTTPError(),
            HTTPError(),
            HTTPError(),
            HTTPError(),
            self.get_successful_jibit_v2_transfer_response(count=0),
        ]
        with pytest.raises(HTTPError):
            call_command('fetch_jibit_history', api_version=2, mode='withdraw')


class FixJibitHistoryCommandTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.deposit = ShetabDeposit.objects.create(
            pk=123, broker=ShetabDeposit.BROKER.jibit_v2, user_id=201, amount=100000,
        )
        bank_account = BankAccount.get_generic_system_account()
        wallet = Wallet.get_user_wallet(bank_account.user, RIAL)
        cls.withdraw = WithdrawRequest.objects.create(pk=123, wallet=wallet, target_account=bank_account, amount=100000)
        cls.daily_withdraw = DailyWithdraw.objects.create(
            broker=DailyWithdraw.BROKER.jibit_v2,
            transfer_pk='123',
            destination='IR000100000000000888888881',
            amount=99000,
            bank_transfer='14001119012243308384',
        )

    def test_run_fix_for_right_withdraw(self):
        call_command('fix_jibit_history')
        self.daily_withdraw.refresh_from_db()
        assert self.daily_withdraw.withdraw == self.withdraw

    def test_run_fix_for_wrong_iban(self):
        DailyWithdraw.objects.filter(pk=self.daily_withdraw.pk).update(destination='IR000100000000000888888882')
        call_command('fix_jibit_history')
        self.daily_withdraw.refresh_from_db()
        assert not self.daily_withdraw.withdraw

    def test_run_fix_for_wrong_amount(self):
        DailyWithdraw.objects.filter(pk=self.daily_withdraw.pk).update(amount=90000)
        call_command('fix_jibit_history')
        self.daily_withdraw.refresh_from_db()
        assert not self.daily_withdraw.withdraw

    def test_run_fix_for_wrong_pk(self):
        DailyWithdraw.objects.filter(pk=self.daily_withdraw.pk).update(transfer_pk='120')
        call_command('fix_jibit_history')
        self.daily_withdraw.refresh_from_db()
        assert not self.daily_withdraw.withdraw
