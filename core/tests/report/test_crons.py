from decimal import Decimal
from unittest.mock import MagicMock, call, patch

from django.test import TestCase
from django.utils import timezone

from exchange.accounts.models import BankAccount, User
from exchange.base.models import RIAL
from exchange.report.crons import (
    DailyWithdrawsManuallyFailedV2,
    SaveDailyDepositsV2,
    SaveDailyWithdrawsV2,
    SaveJibitBankDeposits,
)
from exchange.report.models import DailyJibitDeposit, DailyShetabDeposit, DailyWithdraw
from exchange.shetab.models import JibitAccount, JibitDeposit, JibitPaymentId, ShetabDeposit
from exchange.wallet.models import BankDeposit, Wallet, WithdrawRequest


class SaveDailyDepositsV2Test(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.deposit = ShetabDeposit.objects.create(
            pk=123, broker=ShetabDeposit.BROKER.jibit_v2, user_id=201, amount=100000,
        )

    @staticmethod
    def get_successful_jibit_token_mock():
        request = MagicMock()
        request.json.return_value = {
            'accessToken': 'access-token',
            'refreshToken': 'refresh-token'
        }
        return request

    @staticmethod
    def get_successful_jibit_purchase_mock(status=None, amount=None):
        request = MagicMock()
        today = timezone.now().date()
        request.json.return_value = {
            'pageNumber': 1,
            'size': 20,
            'numberOfElements': 1,
            'hasNext': False,
            'hasPrevious': False,
            'elements': [{
                'purchaseId': 1200,
                'amount': amount or 100000,
                'wage': 5000,
                'fee': 4555,
                'feePaymentType': 'POST_PAID',
                'currency': 'IRR',
                'wltBalance': 100000,
                'feeBalance': 1111,
                'shwBalance': 3333,
                'callbackUrl': 'https://www.client.ir/purchases/123456789/callback',
                'state': status or 'READY_TO_VERIFY',
                'clientReferenceNumber': 'nobitex123',
                'pspRrn': '84a29cbb205c4aa18dc71b8e3cb99639',
                'pspReferenceNumber': 'GmshtyjwKSsoD4uz5cpmzY5aBaWxx21mxAYRo92Gx0',
                'pspTraceNumber': 'psp-trace-num',
                'expirationDate': '2022-02-01T10:17:41.095731Z',
                'userIdentifier': '201',
                'payerMobileNumber': '09132517905',
                'payerCardNumber': '434567-3452',
                'payerNationalCode': '4060145796',
                'description': 'nobitex123',
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
            }]
        }
        return request

    @patch('exchange.shetab.handlers.jibit.requests')
    def test_daily_deposit_cron_existing_record(self, jibit_api_mock=None):
        jibit_api_mock.post.return_value = self.get_successful_jibit_token_mock()
        jibit_api_mock.get.return_value = self.get_successful_jibit_purchase_mock()
        assert not DailyShetabDeposit.objects.exists()
        SaveDailyDepositsV2().run()
        logs = DailyShetabDeposit.objects.all()
        assert len(logs) == 1
        assert Decimal(logs[0].amount) == self.deposit.amount
        assert logs[0].deposit == self.deposit

    @patch('exchange.shetab.handlers.jibit.requests')
    def test_daily_deposit_cron_nonexistent_record(self, jibit_api_mock=None):
        jibit_api_mock.post.return_value = self.get_successful_jibit_token_mock()
        jibit_api_mock.get.return_value = self.get_successful_jibit_purchase_mock()
        ShetabDeposit.objects.all().delete()
        assert not DailyShetabDeposit.objects.exists()
        SaveDailyDepositsV2().run()
        assert DailyShetabDeposit.objects.count() == 1
        log = DailyShetabDeposit.objects.first()
        assert log.deposit is None

    @patch('exchange.shetab.handlers.jibit.requests')
    def test_daily_deposit_cron_double_run_no_change(self, jibit_api_mock=None):
        jibit_api_mock.post.return_value = self.get_successful_jibit_token_mock()
        jibit_api_mock.get.return_value = self.get_successful_jibit_purchase_mock()
        assert not DailyShetabDeposit.objects.exists()
        SaveDailyDepositsV2().run()
        assert DailyShetabDeposit.objects.count() == 1
        SaveDailyDepositsV2().run()
        assert DailyShetabDeposit.objects.count() == 1

    @patch('exchange.shetab.handlers.jibit.requests')
    def test_daily_deposit_cron_double_run_status_change(self, jibit_api_mock=None):
        jibit_api_mock.post.return_value = self.get_successful_jibit_token_mock()
        jibit_api_mock.get.return_value = self.get_successful_jibit_purchase_mock(status='IN_PROGRESS')
        assert not DailyShetabDeposit.objects.exists()
        SaveDailyDepositsV2().run()
        assert DailyShetabDeposit.objects.count() == 1
        log = DailyShetabDeposit.objects.first()
        assert log.status == DailyShetabDeposit.STATUS.in_progress
        jibit_api_mock.get.return_value = self.get_successful_jibit_purchase_mock(status='SUCCESS')
        SaveDailyDepositsV2().run()
        assert DailyShetabDeposit.objects.count() == 1
        log.refresh_from_db()
        assert log.status == DailyShetabDeposit.STATUS.success
        jibit_api_mock.get.return_value = self.get_successful_jibit_purchase_mock(status='FAILED')
        assert DailyShetabDeposit.objects.count() == 1
        log.refresh_from_db()
        assert log.status == DailyShetabDeposit.STATUS.success

    @patch('exchange.shetab.handlers.jibit.requests')
    def test_daily_deposit_cron_naughty_amount_change(self, jibit_api_mock=None):
        jibit_api_mock.post.return_value = self.get_successful_jibit_token_mock()
        jibit_api_mock.get.return_value = self.get_successful_jibit_purchase_mock(amount=200000)
        assert not DailyShetabDeposit.objects.exists()
        SaveDailyDepositsV2().run()
        assert DailyShetabDeposit.objects.count() == 1
        log = DailyShetabDeposit.objects.first()
        assert log.deposit is None

    def test_manual_deposit_reference_number_or_user_id(self):
        assert not SaveDailyDepositsV2().get_deposit('MAPI-STL-1SjPL-1111-00', '201', '10000')
        assert not SaveDailyDepositsV2().get_deposit('nobitest45', '201', '10000')
        assert not SaveDailyDepositsV2().get_deposit('nobitex45', 'a.khaksari@gmail.com', '10000')


class SaveDailyWithdrawsV2Test(TestCase):
    @classmethod
    def setUpTestData(cls):
        bank_account = BankAccount.get_generic_system_account()
        wallet = Wallet.get_user_wallet(bank_account.user, RIAL)
        cls.withdraw = WithdrawRequest.objects.create(
            pk=123, wallet=wallet, target_account=bank_account, amount=100000, fee=1000
        )

    @staticmethod
    def get_successful_jibit_token_mock():
        request = MagicMock()
        request.json.return_value = {
            'accessToken': 'access-token',
            'refreshToken': 'refresh-token'
        }
        return request

    @staticmethod
    def get_successful_jibit_transfer_mock(status=None, amount=None):
        request = MagicMock()
        today = timezone.now().date()
        request.json.return_value = {
            'page': 1,
            'size': 20,
            'elements': [
                {
                    'transferID': '123',
                    'transferMode': 'NORMAL',
                    'destination': 'IR000100000000000888888881',
                    'destinationFirstName': 'Ali',
                    'destinationLastName': 'Khaksari',
                    'amount': amount or 99000,
                    'currency': 'RIALS',
                    'paymentID': '9900080478337192',
                    'description': 'واریز 123 از نوبیتکس',
                    'metadata': {'someTag': 'some-value'},
                    'notifyURL': 'https://www.client.ir/purchases/123456789/notify',
                    'cancellable': False,
                    'bankTransferID': '14001119012243308384',
                    'state': status or 'IN_PROGRESS',
                    'failReason': None,
                    'feeCurrency': 'IRR',
                    'feeAmount': 10900,
                    'createdAt': f'{today}T06:38:23.617287Z',
                    'modifiedAt': f'{today}T07:41:26.625254Z',
                }
            ],
        }
        return request

    @staticmethod
    def get_no_jibit_transfer_mock():
        request = MagicMock()
        request.json.return_value = {
            'page': 1,
            'size': 20,
            'elements': []
        }
        return request

    @patch('exchange.wallet.settlement.requests')
    def test_daily_withdraw_cron_existing_record(self, jibit_api_mock=None):
        jibit_api_mock.post.return_value = self.get_successful_jibit_token_mock()
        jibit_api_mock.get.side_effect = [self.get_successful_jibit_transfer_mock(), self.get_no_jibit_transfer_mock()]
        assert not DailyWithdraw.objects.exists()
        SaveDailyWithdrawsV2().run()
        logs = DailyWithdraw.objects.all()
        assert len(logs) == 1
        assert Decimal(logs[0].amount) == self.withdraw.amount - self.withdraw.fee
        assert logs[0].withdraw == self.withdraw

    @patch('exchange.wallet.settlement.requests')
    def test_daily_withdraw_cron_nonexistent_record(self, jibit_api_mock=None):
        jibit_api_mock.post.return_value = self.get_successful_jibit_token_mock()
        jibit_api_mock.get.side_effect = [self.get_successful_jibit_transfer_mock(), self.get_no_jibit_transfer_mock()]
        WithdrawRequest.objects.all().delete()
        assert not DailyWithdraw.objects.exists()
        SaveDailyWithdrawsV2().run()
        assert DailyWithdraw.objects.count() == 1
        log = DailyWithdraw.objects.first()
        assert log.withdraw is None

    @patch('exchange.wallet.settlement.requests')
    def test_daily_withdraw_cron_double_run_no_change(self, jibit_api_mock=None):
        jibit_api_mock.post.return_value = self.get_successful_jibit_token_mock()
        jibit_api_mock.get.side_effect = [self.get_successful_jibit_transfer_mock(), self.get_no_jibit_transfer_mock()]
        assert not DailyWithdraw.objects.exists()
        SaveDailyWithdrawsV2().run()
        assert DailyWithdraw.objects.count() == 1
        # first call starts from 7 days ago
        assert jibit_api_mock.get.call_args[1]['params']['from'].endswith(':30:00Z')
        SaveDailyWithdrawsV2().run()
        assert DailyWithdraw.objects.count() == 1
        # second call starts first withdraw in progress
        assert jibit_api_mock.get.call_args[1]['params']['from'].endswith('T06:38:23.617287Z')

    @patch('exchange.wallet.settlement.requests')
    def test_daily_withdraw_cron_double_run_status_change(self, jibit_api_mock=None):
        jibit_api_mock.post.return_value = self.get_successful_jibit_token_mock()
        jibit_api_mock.get.side_effect = [
            self.get_successful_jibit_transfer_mock(status='IN_PROGRESS'), self.get_no_jibit_transfer_mock()
        ]
        assert not DailyWithdraw.objects.exists()
        SaveDailyWithdrawsV2().run()
        assert DailyWithdraw.objects.count() == 1
        log = DailyWithdraw.objects.first()
        assert log.status == DailyWithdraw.STATUS.in_progress
        jibit_api_mock.get.side_effect = [
            self.get_successful_jibit_transfer_mock(status='TRANSFERRED'), self.get_no_jibit_transfer_mock()
        ]
        SaveDailyWithdrawsV2().run()
        assert DailyWithdraw.objects.count() == 1
        log.refresh_from_db()
        assert log.status == DailyWithdraw.STATUS.transferred
        jibit_api_mock.get.side_effect = [
            self.get_successful_jibit_transfer_mock(status='FAILED'), self.get_no_jibit_transfer_mock()
        ]
        assert DailyWithdraw.objects.count() == 1
        log.refresh_from_db()
        assert log.status == DailyWithdraw.STATUS.transferred

    @patch('exchange.wallet.settlement.requests')
    def test_daily_withdraw_cron_naughty_amount_change(self, jibit_api_mock=None):
        jibit_api_mock.post.return_value = self.get_successful_jibit_token_mock()
        jibit_api_mock.get.side_effect = [
            self.get_successful_jibit_transfer_mock(amount=200000), self.get_no_jibit_transfer_mock()
        ]
        assert not DailyWithdraw.objects.exists()
        SaveDailyWithdrawsV2().run()
        assert DailyWithdraw.objects.count() == 1
        log = DailyWithdraw.objects.first()
        assert log.withdraw is None

    def test_manual_withdraw_transfer_id(self):
        assert not SaveDailyWithdrawsV2().get_withdraw(
            'MAPI-STL-1SjPL-1111-00',
            'IR000100000000000888888881',
            '10000',
        )

    def test_manual_withdraw_transfer_id_with_payment_id(self):
        assert not SaveDailyWithdrawsV2().get_withdraw(
            self.withdraw.pk, 'IR000100000000000888899999', '99000', '9900080478337192'
        )
        self.withdraw.target_account.shaba_number = '9900080478337192'
        self.withdraw.target_account.save()
        withdraw = SaveDailyWithdrawsV2().get_withdraw(
            self.withdraw.pk, 'IR000100000000000888899999', '99000', '9900080478337192'
        )
        assert withdraw.pk == self.withdraw.pk

class SaveDailyWithdrawsV2Test(TestCase):
    @classmethod
    def setUpTestData(cls):
        bank_account = BankAccount.get_generic_system_account()
        wallet = Wallet.get_user_wallet(bank_account.user, RIAL)
        cls.withdraw = WithdrawRequest.objects.create(
            pk=123, wallet=wallet, target_account=bank_account, amount=100000, fee=1000
        )

    @staticmethod
    def get_successful_jibit_token_mock():
        request = MagicMock()
        request.json.return_value = {
            'accessToken': 'access-token',
            'refreshToken': 'refresh-token'
        }
        return request

    @staticmethod
    def get_successful_jibit_transfer_mock(status=None, amount=None):
        request = MagicMock()
        today = timezone.now().date()
        request.json.return_value = {
            'page': 1,
            'size': 20,
            'elements': [
                {
                    'transferID': '123',
                    'transferMode': 'NORMAL',
                    'destination': 'IR000100000000000888888881',
                    'destinationFirstName': 'Ali',
                    'destinationLastName': 'Khaksari',
                    'amount': amount or 99000,
                    'currency': 'RIALS',
                    'paymentID': '9900080478337192',
                    'description': 'واریز 123 از نوبیتکس',
                    'metadata': {'someTag': 'some-value'},
                    'notifyURL': 'https://www.client.ir/purchases/123456789/notify',
                    'cancellable': False,
                    'bankTransferID': '14001119012243308384',
                    'state': status or 'MANUALLY_FAILED',
                    'failReason': None,
                    'feeCurrency': 'IRR',
                    'feeAmount': 10900,
                    'createdAt': f'{today}T06:38:23.617287Z',
                    'modifiedAt': f'{today}T07:41:26.625254Z',
                }
            ],
        }
        return request

    @staticmethod
    def get_no_jibit_transfer_mock():
        request = MagicMock()
        request.json.return_value = {
            'page': 1,
            'size': 20,
            'elements': []
        }
        return request

    @patch('exchange.wallet.settlement.requests')
    @patch('exchange.report.crons.run_admin_task')
    def test_daily_withdraw_cron_existing_record(self, run_admin_task_mock: MagicMock, jibit_api_mock=None):
        jibit_api_mock.post.return_value = self.get_successful_jibit_token_mock()
        jibit_api_mock.get.side_effect = [self.get_successful_jibit_transfer_mock(), self.get_no_jibit_transfer_mock()]
        assert not DailyWithdraw.objects.exists()

        response = self.get_successful_jibit_transfer_mock().json.return_value['elements'][0]
        response['state'] = 'TRANSFERRED'
        data = DailyWithdrawsManuallyFailedV2.parse_item(response)
        DailyWithdrawsManuallyFailedV2.model.objects.get_or_create(**data)
        logs = DailyWithdraw.objects.all()
        assert len(logs) == 1
        DailyWithdrawsManuallyFailedV2().run()
        assert len(logs) == 1
        run_admin_task_mock.assert_has_calls(calls=[
            call('admin.daily_withdraw_manually_failed', daily_withdraw_ids=[logs.get().id])
        ])
        assert Decimal(logs[0].amount) == self.withdraw.amount - self.withdraw.fee
        assert logs[0].withdraw == self.withdraw


class SaveJibitBankDepositsTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        bank_account = BankAccount.get_generic_system_account()
        cls.user = User.objects.create_user('SaveJibitBankDepositsTest')
        cls.bank_deposit = BankDeposit.objects.create(
            deposited_at=timezone.now(),
            user_id=cls.user.pk,
            src_bank_account=bank_account,
            receipt_id='test_receipt_id',
            dst_bank_account='test_dst_bank_account',
            amount=49500,
        )
        cls.jibit_account = JibitAccount.objects.create(
            iban='default_iban', owner_name='test_owner_name',
        )
        cls.payment_id = JibitPaymentId.objects.create(
            bank_account=bank_account, jibit_account=cls.jibit_account, payment_id='9900080467339119',
        )
        cls.jibit_deposit = JibitDeposit.objects.create(
            external_reference_number='PIP2-862489898254827538',
            bank_reference_number='233046',
            bank_deposit=cls.bank_deposit, amount=49500,
            payment_id=cls.payment_id,
        )

    @staticmethod
    def get_successful_jibit_token_mock():
        request = MagicMock()
        request.json.return_value = {
            'accessToken': 'access-token',
            'refreshToken': 'refresh-token'
        }
        return request

    @staticmethod
    def get_successful_jibit_pip_mock(status=None, amount=None):
        request = MagicMock()
        request.json.return_value = {
            'content': [
                {
                    'externalReferenceNumber': 'PIP2-862489898254827538',
                    'status': 'FAILED',
                    'bank': 'BKMTIR',
                    'bankReferenceNumber': '233046',
                    'paymentId': '9900080467339119',
                    'merchantReferenceNumber': 'testnobitex001',
                    'amount': 49500,
                    'sourceIdentifier': 'IR740120020000009367139939',
                    'destinationAccountIdentifier': 'IR760120020000008992439961',
                    'rawBankTimestamp': '1402/2/15 13:32:49'
                },
                {
                    'externalReferenceNumber': 'PIP2-862295520902348816',
                    'status': f'{status or "WAITING_FOR_MERCHANT_VERIFY"}',
                    'bank': 'BKMTIR',
                    'bankReferenceNumber': '21330243',
                    'paymentId': '9900080467339119',
                    'merchantReferenceNumber': 'testnobitex001',
                    'amount': 544500,
                    'sourceIdentifier': 'IR740120020000009367139939',
                    'destinationAccountIdentifier': 'IR760120020000008992439961',
                    'rawBankTimestamp': '1402/2/14 21:6:11'
                },
                {
                    'externalReferenceNumber': 'PIP2-855992278469967888',
                    'status': 'FAILED',
                    'bank': 'BKMTIR',
                    'bankReferenceNumber': '2914658',
                    'paymentId': '9900080468214190',
                    'merchantReferenceNumber': 'testnobitex002',
                    'amount': 200000,
                    'sourceIdentifier': 'IR040620000000203503182003',
                    'destinationAccountIdentifier': 'IR760120020000008992439961',
                    'rawBankTimestamp': '1402/1/23 14:40:22'
                },
                {
                    'externalReferenceNumber': 'PIP2-855686071866064911',
                    'status': 'SUCCESSFUL',
                    'bank': 'BKMTIR',
                    'bankReferenceNumber': '21408264',
                    'paymentId': '9900080468377135',
                    'merchantReferenceNumber': 'nobitextest0101',
                    'amount': 153450,
                    'sourceIdentifier': 'IR020120020000008254600220',
                    'destinationAccountIdentifier': 'IR760120020000008992439961',
                    'rawBankTimestamp': '1402/1/22 12:48:14'
                },
                {
                    'externalReferenceNumber': 'PIP2-855640438693199886',
                    'status': 'SUCCESSFUL',
                    'bank': 'BKMTIR',
                    'bankReferenceNumber': '22038125',
                    'paymentId': '9900080468377135',
                    'merchantReferenceNumber': 'nobitextest0101',
                    'amount': 148500,
                    'sourceIdentifier': 'IR020120020000000465049364',
                    'destinationAccountIdentifier': 'IR760120020000008992439961',
                    'rawBankTimestamp': '1402/1/21 22:12:1'
                }
            ],
            'pageable': {
                'sort': {
                    'sorted': False,
                    'unsorted': True,
                    'empty': True
                },
                'offset': 0,
                'pageNumber': 0,
                'pageSize': 50,
                'paged': True,
                'unpaged': False
            },
            'totalPages': 1,
            'last': True,
            'sort': {
                'sorted': False,
                'unsorted': True,
                'empty': True
            },
            'size': 50,
            'number': 0,
            'first': True,
            'empty': False
        }
        return request

    @patch('exchange.shetab.handlers.jibit.requests')
    def test_daily_jibit_deposit_cron_existing_record(self, jibit_api_mock=None):
        jibit_api_mock.post.return_value = self.get_successful_jibit_token_mock()
        jibit_api_mock.get.return_value = self.get_successful_jibit_pip_mock()
        assert not DailyJibitDeposit.objects.exists()
        SaveJibitBankDeposits().run()
        logs = DailyJibitDeposit.objects.all()
        assert logs.count() == 5
        log = DailyJibitDeposit.objects.filter(external_reference_number='PIP2-862489898254827538').first()
        assert Decimal(log.amount) == self.jibit_deposit.amount
        assert log.jibit_deposit == self.jibit_deposit
        assert log.jibit_deposit.bank_deposit == self.bank_deposit

    @patch('exchange.shetab.handlers.jibit.requests')
    def test_daily_jibit_deposit_cron_nonexistent_record(self, jibit_api_mock=None):
        jibit_api_mock.post.return_value = self.get_successful_jibit_token_mock()
        jibit_api_mock.get.return_value = self.get_successful_jibit_pip_mock()
        assert not DailyJibitDeposit.objects.exists()
        JibitDeposit.objects.all().delete()
        SaveJibitBankDeposits().run()
        log = DailyJibitDeposit.objects.first()
        assert log.jibit_deposit is None

    @patch('exchange.shetab.handlers.jibit.requests')
    def test_daily_jibit_deposit_cron_double_run_no_change(self, jibit_api_mock=None):
        jibit_api_mock.post.return_value = self.get_successful_jibit_token_mock()
        jibit_api_mock.get.return_value = self.get_successful_jibit_pip_mock()
        assert not DailyJibitDeposit.objects.exists()
        SaveJibitBankDeposits().run()
        logs = DailyJibitDeposit.objects.all()
        assert logs.count() == 5
        logs = DailyJibitDeposit.objects.all()
        assert logs.count() == 5

    @patch('exchange.shetab.handlers.jibit.requests')
    def test_daily_jibit_deposit_cron_double_run_status_change(self, jibit_api_mock=None):
        jibit_api_mock.post.return_value = self.get_successful_jibit_token_mock()
        jibit_api_mock.get.return_value = self.get_successful_jibit_pip_mock()
        logs = DailyJibitDeposit.objects.all()
        assert not DailyJibitDeposit.objects.exists()
        SaveJibitBankDeposits().run()
        assert logs.count() == 5
        assert set(logs.values_list('status', flat=True).distinct()) == {
            DailyJibitDeposit.STATUS.waiting_for_merchant_verify,
            DailyJibitDeposit.STATUS.successful,
            DailyJibitDeposit.STATUS.failed,
        }
        jibit_api_mock.get.return_value = self.get_successful_jibit_pip_mock(status='IN_PROGRESS')
        SaveJibitBankDeposits().run()
        assert logs.count() == 5
        assert set(logs.values_list('status', flat=True).distinct()) == {
            DailyJibitDeposit.STATUS.in_progress,
            DailyJibitDeposit.STATUS.successful,
            DailyJibitDeposit.STATUS.failed,
        }
        jibit_api_mock.get.return_value = self.get_successful_jibit_pip_mock(status='SUCCESSFUL')
        SaveJibitBankDeposits().run()
        assert logs.count() == 5
        assert set(logs.values_list('status', flat=True).distinct()) == {
            DailyJibitDeposit.STATUS.successful,
            DailyJibitDeposit.STATUS.failed,
        }
