import copy
import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

from django.test import TestCase, TransactionTestCase, override_settings
from requests import HTTPError
from requests.models import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from exchange.accounts.models import Notification, User, UserSms
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings
from exchange.base.serializers import serialize
from exchange.direct_debit.constants import DEFAULT_MIN_DEPOSIT_AMOUNT, FaraboomContractStatus
from exchange.direct_debit.crons import DirectDebitCheckTimeoutDepositCron
from exchange.direct_debit.exceptions import ThirdPartyConnectionError
from exchange.direct_debit.models import DirectDebitContract, DirectDeposit
from exchange.wallet.models import Transaction, Wallet
from tests.base.utils import TransactionTestFastFlushMixin
from tests.direct_debit.helper import DirectDebitMixins, MockResponse


class DirectDepositAPITest(APITestCase, DirectDebitMixins):
    fixtures = ('test_data',)

    @property
    def sample_faraboom_response(self):
        return {
            'reference_id': '00001711362456900488',
            'trace_id': '26e2edb8aa894be7823a3b0d96303370',
            'transaction_amount': 1000000,
            'transaction_time': 1711362478164,
            'batch_id': 872057,
            'commission_amount': 0,
            'status': 'SUCCEED',
            'details': [
                {
                    'reference_id': '00001711362456900488',
                    'trace_id': '26e2edb8aa894be7823a3b0d96303370_1',
                    'amount': 1000000,
                    'transaction_time': 1711349878139,
                    'transaction_detail_type': 'MAIN',
                    'status': 'SUCCEED',
                }
            ],
            'is_over_draft': False,
        }

    @property
    def sample_faraboom_response_instant_payment(self):
        instant_payment_response = copy.copy(self.sample_faraboom_response)
        instant_payment_response.pop('batch_id')
        return instant_payment_response

    def setUp(self):
        super().setUp()
        self.user = User.objects.get(id=201)
        self.user.user_type = User.USER_TYPE_LEVEL1
        self.user.save()

        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.request_feature(self.user, 'done')
        self.contract = self.create_contract(user=self.user)
        self.contract.trace_id = 'cdklcdke-b7jk-5hg-997c-b991acdac3b6'
        self.contract.contract_id = 'kr7JBZLrkMNZ'
        self.contract.save()
        vp = self.user.get_verification_profile()
        vp.mobile_confirmed = True
        vp.mobile_identity_confirmed = True
        vp.email_confirmed = True
        vp.save()
        self.user.mobile = '09151234567'
        self.user.save()

    @patch('exchange.direct_debit.models.transaction.on_commit', lambda t: t())
    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_deposit_successfully(self, mock_direct_deposit_response):
        mock_direct_deposit_response.return_value = MockResponse(self.sample_faraboom_response, status.HTTP_200_OK)
        url = '/direct-debit/deposit'
        data = {'amount': 1000000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        deposit = DirectDeposit.objects.filter(contract=self.contract, amount=1000000).first()
        assert deposit
        assert deposit.third_party_response == self.sample_faraboom_response
        expected = {
            'deposit': {
                'amount': '1000000',
                'date': serialize(deposit.effective_date),
                'fee': '10000',
                'id': deposit.id,
                'status': 'Succeed',
                'traceID': deposit.trace_id,
                'referenceID': deposit.reference_id,
                'depositType': 'directDeposit',
                'bank': {
                    'id': self.contract.bank.id,
                    'bankID': self.contract.bank.bank_id,
                    'bankName': self.contract.bank.name,
                    'isActive': self.contract.bank.is_active,
                },
            },
            'status': 'ok',
        }
        assert output == expected
        assert len(deposit.details) == 1
        assert deposit.fee == Decimal('10000.0000000000')
        assert deposit.status == DirectDeposit.STATUS.succeed
        assert deposit.reference_id == '00001711362456900488'
        transaction = Transaction.objects.filter(ref_module=302, ref_id=deposit.pk).first()
        assert transaction.amount == Decimal('990000.0000000000')
        assert transaction.wallet == Wallet.get_user_wallet(self.user, Currencies.rls)
        assert transaction.description == 'واریز مستقیم - {} - شماره پیگیری: {}'.format(
            self.contract.bank.name, deposit.trace_id
        )
        notification = Notification.objects.filter(user=self.user).last()
        assert (
            notification.message == f'مبلغ 99000 تومان '
                                    f'از حساب {deposit.contract.bank.name}'
                                    f' به کیف پول اسپات شما واریز مستقیم شد.'
        )
        sms = UserSms.objects.filter(user=self.user).first()
        assert sms
        assert sms.text == self.contract.bank.name
        assert sms.template == UserSms.TEMPLATES.direct_debit_deposit_successfully
        assert sms.tp == UserSms.TYPES.direct_debit_deposit

    @patch('exchange.direct_debit.models.transaction.on_commit', lambda t: t())
    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_deposit_successfully_instant_payment(self, mock_direct_deposit_response):
        mock_direct_deposit_response.return_value = MockResponse(
            self.sample_faraboom_response_instant_payment,
            status.HTTP_200_OK,
        )
        url = '/direct-debit/deposit'
        data = {'amount': 1000000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        deposit = DirectDeposit.objects.filter(contract=self.contract, amount=1000000).first()
        assert deposit
        expected = {
            'deposit': {
                'amount': '1000000',
                'date': serialize(deposit.effective_date),
                'fee': '10000',
                'id': deposit.id,
                'status': 'Succeed',
                'traceID': deposit.trace_id,
                'referenceID': deposit.reference_id,
                'depositType': 'directDeposit',
                'bank': {
                    'id': self.contract.bank.id,
                    'bankID': self.contract.bank.bank_id,
                    'bankName': self.contract.bank.name,
                    'isActive': self.contract.bank.is_active,
                },
            },
            'status': 'ok',
        }
        assert output == expected
        assert len(deposit.details) == 1
        assert deposit.fee == Decimal('10000.0000000000')
        assert not deposit.batch_id
        transaction = Transaction.objects.filter(ref_module=302, ref_id=deposit.pk).first()
        assert transaction.amount == Decimal('990000.0000000000')
        assert transaction.wallet == Wallet.get_user_wallet(self.user, Currencies.rls)
        assert transaction.description == 'واریز مستقیم - {} - شماره پیگیری: {}'.format(
            self.contract.bank.name, deposit.trace_id
        )
        notification = Notification.objects.filter(user=self.user).last()
        assert (
            notification.message == f'مبلغ 99000 تومان از حساب '
            f'{self.contract.bank.name}'
            f' به کیف پول اسپات شما واریز مستقیم شد.'
        )

    def test_over_max_daily_amount_in_contract(self):
        self.create_deposit(self.user, self.contract, Decimal('5_000_000_0'))
        self.create_deposit(self.user, self.contract, Decimal('5_000_000_0'))
        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'DailyAmountExceededError',
            'message': 'The amount is out of range of the total daily amount in your contract.',
            'status': 'failed',
        }

    @patch('exchange.direct_debit.models.transaction.on_commit', lambda t: t())
    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_over_max_daily_amount_in_contract_raised_by_provider(self, mock_direct_deposit_response):
        self.mock_faraboom_deposit_error(
            mock_direct_deposit_response,
            error_code='2144',
            error_message='محدودیت مقداری روزانه نقض شده است.',
        )
        self.create_deposit(self.user, self.contract, Decimal('5_000_000_0'))
        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'DailyAmountExceededError',
            'message': 'The amount is out of range of the total daily amount in your contract.',
            'status': 'failed',
        }

    def test_over_max_daily_count_transaction_in_contract(self):
        self.create_deposit(self.user, self.contract, Decimal('5_000_000_0'))
        self.create_deposit(self.user, self.contract, Decimal('4_000_000_0'))
        self.contract.daily_max_transaction_count = 2
        self.contract.save()
        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'DailyCountExceededError',
            'message': 'The number of transactions is out of range of the total daily amount in your contract.',
            'status': 'failed',
        }

    def test_over_max_amount_transaction_of_the_bank(self):
        bank = self.create_bank(max_transaction_amount=Decimal('9_000_0'))
        self.contract.bank = bank
        self.contract.save()
        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'MaxAmountBankExceededError',
            'message': 'The amount of transactions is greater than the bank maximum transaction amount.',
            'status': 'failed',
        }

    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_max_daily_count_transaction_in_contract_without_limit_of_contract(self, mock_direct_deposit_response):
        self.create_deposit(self.user, self.contract, Decimal('5_000_000_0'))
        self.create_deposit(self.user, self.contract, Decimal('4_000_000_0'))
        self.contract.daily_max_transaction_count = 1
        self.contract.save()
        mock_direct_deposit_response.return_value = MockResponse(self.sample_faraboom_response, status.HTTP_200_OK)
        url = '/direct-debit/deposit'
        data = {'amount': 1000000, 'contract': self.contract.id}
        output = self.client.post(url, data).json()
        expected_output = {
            'status': 'failed',
            'code': 'DailyCountExceededError',
            'message': 'The number of transactions is out of range of the total daily amount in your contract.',
        }
        assert output == expected_output
        self.contract.daily_max_transaction_count = 0
        self.contract.save()

        output = self.client.post(url, data).json()

        deposit = DirectDeposit.objects.filter(contract=self.contract, amount=1000000).order_by('-created_at').first()
        expected = {
            'deposit': {
                'amount': '1000000',
                'date': serialize(deposit.effective_date),
                'fee': '10000',
                'id': deposit.id,
                'status': 'Succeed',
                'traceID': deposit.trace_id,
                'referenceID': deposit.reference_id,
                'depositType': 'directDeposit',
                'bank': {
                    'id': self.contract.bank.id,
                    'bankName': self.contract.bank.name,
                    'bankID': self.contract.bank.bank_id,
                    'isActive': self.contract.bank.is_active,
                },
            },
            'status': 'ok',
        }
        assert output == expected

    def test_max_transaction_amount(self):
        self.contract.max_transaction_amount = Decimal('100_000_0')
        self.contract.save()
        url = '/direct-debit/deposit'
        data = {'amount': 1000001, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'MaxAmountExceededError',
            'message': 'The amount of transactions is greater than the maximum transaction amount in your contract.',
            'status': 'failed',
        }

    def test_min_transaction_amount(self):
        url = '/direct-debit/deposit'
        data = {'amount': '19999', 'contract': self.contract.id}
        Settings.set('direct_debit_min_amount_in_deposit', DEFAULT_MIN_DEPOSIT_AMOUNT)
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'MinAmountNotMetError',
            'message': 'The amount of transactions is lower than the minimum transaction amount',
            'status': 'failed',
        }

    def test_deposit_send_other_user_contract(self):
        user = User.objects.get(id=202)
        new_contract = self.create_contract(user)
        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': new_contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            'code': 'ContractDoesNotExist',
            'message': 'Contract does not exist.',
            'status': 'failed',
        }

    def test_deposit_with_deactivated_contract(self):
        self.contract.status = DirectDebitContract.STATUS.deactive
        self.contract.save()
        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            'code': 'ContractDoesNotExist',
            'message': 'Contract does not exist.',
            'status': 'failed',
        }

    def test_deposit_with_expired_contract(self):
        self.contract.expires_at = ir_now()
        self.contract.save()
        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            'code': 'ContractDoesNotExist',
            'message': 'Contract does not exist.',
            'status': 'failed',
        }

    def test_deposit_with_not_started_contract(self):
        self.contract.started_at = ir_now() + datetime.timedelta(hours=5)
        self.contract.save()
        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            'code': 'ContractDoesNotExist',
            'message': 'Contract does not exist.',
            'status': 'failed',
        }

    def test_deposit_user_eligibility(self):
        self.user.user_type = User.USER_TYPES.level0
        self.user.save()

        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'UserLevelRestriction',
            'message': 'User level does not meet the requirements',
            'status': 'failed',
        }

    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_daily_max_transaction_amount_bank_mellat(self, response_mock):
        user_2 = User.objects.create_user(username='user2')
        self.create_contract(user=user_2)

        mock_response = MockResponse(
            json_data={
                'code': '29003',
                'error': 'سقف تراکنش روزانه پیمان به اتمام رسیده است',
                'errors': [{'code': '29003', 'error': 'سقف تراکنش روزانه پیمان به اتمام رسیده است'}],
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        mock_response.text = 'test_error_text'
        response_mock.side_effect = HTTPError('http_error_msg', response=mock_response)
        url = '/direct-debit/deposit'
        data = {'amount': 300000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'MaxTransactionAmountExceededError',
            'message': 'Max transaction amount exceeded',
            'status': 'failed',
        }
        deposit = DirectDeposit.objects.filter(contract=self.contract, amount=300000).first()
        assert deposit
        assert deposit.status == DirectDeposit.STATUS.failed
        assert deposit.third_party_response == {
            'code': '29003',
            'error': 'سقف تراکنش روزانه پیمان به اتمام رسیده است',
            'errors': [{'code': '29003', 'error': 'سقف تراکنش روزانه پیمان به اتمام رسیده است'}],
        }

    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_insufficient_balance_behaviour_after_two_try(self, response_mock):
        user_2 = User.objects.create_user(username='user2')
        contract = self.create_contract(user=user_2)
        # must be ignored
        DirectDeposit.objects.create(
            status=DirectDeposit.STATUS.insufficient_balance,
            trace_id='adslfhkafygoaisjjlklni',
            contract=contract,
            amount=Decimal('10000000'),
        )
        # must be ignored
        DirectDeposit.objects.create(
            status=DirectDeposit.STATUS.insufficient_balance,
            trace_id='adslfhlhoaliaifgjlklni',
            contract=contract,
            amount=Decimal('10000000'),
        )

        self.mock_faraboom_deposit_error(
            response_mock,
            error_code='003',
            error_message='موجودی سپرده کافی نیست.',
        )
        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': self.contract.id}
        # first try
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'InsufficientBalanceError',
            'message': 'The account balance is insufficient.',
            'status': 'failed',
        }
        # second try
        self.client.post(url, data)
        response_mock.side_effect = None
        response_mock.return_value = MockResponse(self.sample_faraboom_response, status.HTTP_200_OK)
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        deposit = DirectDeposit.objects.filter(contract=self.contract, amount=1000000).first()
        expected = {
            'deposit': {
                'amount': '1000000',
                'date': serialize(deposit.effective_date),
                'fee': '10000',
                'id': deposit.id,
                'status': 'Succeed',
                'traceID': deposit.trace_id,
                'referenceID': deposit.reference_id,
                'depositType': 'directDeposit',
                'bank': {
                    'id': self.contract.bank.id,
                    'bankName': self.contract.bank.name,
                    'bankID': self.contract.bank.bank_id,
                    'isActive': self.contract.bank.is_active,
                },
            },
            'status': 'ok',
        }
        assert response.json() == expected

    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_not_balance_action(self, response_mock):
        self.mock_faraboom_deposit_error(
            response_mock,
            error_code='003',
            error_message='موجودی سپرده کافی نیست.',
        )
        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'InsufficientBalanceError',
            'message': 'The account balance is insufficient.',
            'status': 'failed',
        }
        self.client.post(url, data)
        self.client.post(url, data)
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            'code': 'ContractDoesNotExist',
            'message': 'Contract does not exist.',
            'status': 'failed',
        }
        self.contract.refresh_from_db()
        assert self.contract.status == DirectDebitContract.STATUS.cancelled

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('exchange.direct_debit.models.transaction.on_commit', lambda t: t())
    @patch('exchange.direct_debit.tasks.FaraboomHandler.change_contract_status')
    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_insufficient_balance_behavior_after_max_try_limit(self, response_mock, faraboom_mock):
        # first day (7 day ago)
        deposit = DirectDeposit.objects.create(
            status=DirectDeposit.STATUS.insufficient_balance,
            trace_id=uuid.uuid4().hex,
            contract=self.contract,
            amount=Decimal('10000'),
        )
        deposit.created_at = ir_now() - datetime.timedelta(days=7)
        deposit.save()
        # third day (4 day ago)
        deposit = DirectDeposit.objects.create(
            status=DirectDeposit.STATUS.insufficient_balance,
            trace_id=uuid.uuid4().hex,
            contract=self.contract,
            amount=Decimal('10000'),
        )
        deposit.created_at = ir_now() - datetime.timedelta(days=4)
        deposit.save()
        # sixth day (1 day ago)
        deposit = DirectDeposit.objects.create(
            status=DirectDeposit.STATUS.insufficient_balance,
            trace_id=uuid.uuid4().hex,
            contract=self.contract,
            amount=Decimal('10000'),
        )
        deposit.created_at = ir_now() - datetime.timedelta(days=1)
        deposit.save()

        response_mock.return_value = MockResponse(self.sample_faraboom_response, status.HTTP_200_OK)

        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        self.contract.refresh_from_db()
        assert self.contract.status != DirectDebitContract.STATUS.cancelled
        faraboom_mock.assert_not_called()

        # today
        mock_response = self.mock_faraboom_deposit_error(
            response_mock,
            error_code='003',
            error_message='موجودی سپرده کافی نیست.',
        )
        url = '/direct-debit/deposit'
        data = {'amount': 700000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'InsufficientBalanceError',
            'message': 'The account balance is insufficient.',
            'status': 'failed',
        }
        self.contract.refresh_from_db()
        assert self.contract.status == DirectDebitContract.STATUS.cancelled
        faraboom_mock.assert_called_once_with(
            self.contract.contract_id, FaraboomContractStatus.CANCELLED.value, self.contract.bank.bank_id
        )

        response = self.client.post(url, data)
        deposit = DirectDeposit.objects.get(amount=700000)
        assert deposit
        assert deposit.status == DirectDeposit.STATUS.insufficient_balance
        assert deposit.third_party_response == mock_response.json_data
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            'code': 'ContractDoesNotExist',
            'message': 'Contract does not exist.',
            'status': 'failed',
        }
        self.contract.refresh_from_db()
        assert self.contract.status == DirectDebitContract.STATUS.cancelled

    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_third_party_unexpended_error(self, response_mock):
        response_mock.side_effect = ValueError()
        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json() == {
            'code': 'ThirdPartyClientError',
            'message': 'An error occurred when trying to connect to third-party API',
            'status': 'failed',
        }
        notification = Notification.objects.filter(user=self.user).last()
        assert notification.message == f'واریز مستقیم {self.contract.bank.name} شما انجام نشد.'

    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_third_party_connection_error(self, response_mock):
        cause_exception = Exception("Underlying network failure")
        third_party_error = ThirdPartyConnectionError()
        third_party_error.__cause__ = cause_exception
        response_mock.side_effect = third_party_error

        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json() == {
            'code': 'ThirdPartyClientError',
            'message': 'An error occurred when trying to connect to third-party API',
            'status': 'failed',
        }
        notification = Notification.objects.filter(user=self.user).last()
        assert notification.message == f'واریز مستقیم {self.contract.bank.name} شما انجام نشد.'

        deposit = DirectDeposit.objects.filter(contract=self.contract, amount=100000).first()
        assert deposit.status == DirectDeposit.STATUS.timeout
        assert deposit.third_party_response == {'error_response': 'Underlying network failure'}

    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_deposit_when_max_transaction_amount_is_null(self, mock_direct_deposit_response):
        mock_direct_deposit_response.return_value = MockResponse(self.sample_faraboom_response, status.HTTP_200_OK)
        self.contract.max_transaction_amount = None
        self.contract.save()
        url = '/direct-debit/deposit'
        data = {'amount': 1000000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        assert DirectDeposit.objects.filter(contract=self.contract, amount=1000000).exists()

    @patch('exchange.direct_debit.models.transaction.on_commit', lambda t: t())
    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_deposit_when_daily_max_transaction_amount_is_null(self, mock_direct_deposit_response):
        mock_direct_deposit_response.return_value = MockResponse(self.sample_faraboom_response, status.HTTP_200_OK)
        self.contract.daily_max_transaction_amount = None
        self.contract.save()
        url = '/direct-debit/deposit'
        data = {'amount': 1000000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        assert DirectDeposit.objects.filter(contract=self.contract, amount=1000000).exists()

    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_deposit_with_random_faraboom_error(self, mock_direct_deposit_response):
        mock_response = self.mock_faraboom_deposit_error(
            mock_direct_deposit_response,
            error_code='2057',
            error_message='بانک مبدا فعال نیست.',
        )
        response = self.perform_deposit_request(amount=200000)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        deposit = DirectDeposit.objects.filter(contract=self.contract, amount=200000).first()
        assert deposit
        assert deposit.status == DirectDeposit.STATUS.failed
        assert deposit.third_party_response == mock_response.json_data

    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_deposit_generic_exception(self, mock_direct_deposit):
        mock_direct_deposit.side_effect = Exception('Unexpected error occurred')

        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertDictEqual(
            response.json(),
            {
                'code': 'ThirdPartyClientError',
                'message': 'An error occurred when trying to connect to third-party API',
                'status': 'failed',
            },
        )

        deposit = DirectDeposit.objects.filter(contract=self.contract, amount=100000).first()
        self.assertIsNotNone(deposit)
        self.assertEqual(deposit.status, DirectDeposit.STATUS.failed)

        notification = Notification.objects.filter(user=self.user).last()
        self.assertEqual(notification.message, f'واریز مستقیم {self.contract.bank.name} شما انجام نشد.')
        assert deposit.third_party_response == {'error_response': 'Unexpected error occurred'}

    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_response_with_invalid_json(self, mock_direct_deposit):
        mock_response = Response()
        mock_response.status_code = status.HTTP_400_BAD_REQUEST
        mock_response._content = b"Non-JSON response"
        mock_response.reason = "Bad Request"

        mock_http_error = HTTPError(response=mock_response)
        mock_direct_deposit.side_effect = mock_http_error

        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': self.contract.id}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        deposit = DirectDeposit.objects.filter(contract=self.contract, amount=100000).first()
        assert deposit is not None
        assert deposit.status == DirectDeposit.STATUS.failed
        assert deposit.third_party_response == {'error_response': 'Non-JSON response'}

    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_deposit_with_expired_card_error(self, mock_direct_deposit_response):
        mock_response = self.mock_faraboom_deposit_error(
            mock_direct_deposit_response,
            error_code='2218',
            error_message='تاریخ انقضای کارت منقضی شده است',
        )
        response = self.perform_deposit_request(amount=100001)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        deposit = DirectDeposit.objects.filter(contract=self.contract, amount=100001).first()
        assert deposit
        assert deposit.status == DirectDeposit.STATUS.failed
        assert deposit.third_party_response == mock_response.json_data

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('exchange.direct_debit.models.transaction.on_commit', lambda t: t())
    @patch('exchange.direct_debit.tasks.FaraboomHandler.change_contract_status')
    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def run_contract_deactivated_test_with_error(
        self, mock_deposit_response, mock_change_status, error_code, error_message
    ):
        mock_response = self.mock_faraboom_deposit_error(
            mock_deposit_response,
            error_code=error_code,
            error_message=error_message,
        )
        mock_change_status.return_value = MockResponse({}, status.HTTP_200_OK)

        response = self.perform_deposit_request(amount=100002)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'status': 'failed',
            'code': 'ContractCanceledInBankError',
            'message': 'This contract has been canceled in the bank.',
        }

        self.contract.refresh_from_db()
        mock_change_status.assert_called_once_with(
            self.contract.contract_id, FaraboomContractStatus.DEACTIVE.value, self.contract.bank.bank_id
        )
        assert self.contract.status == self.contract.STATUS.deactive

        deposit = DirectDeposit.objects.filter(contract=self.contract, amount=100002).first()
        assert deposit
        assert deposit.status == DirectDeposit.STATUS.failed
        assert deposit.third_party_response == mock_response.json_data
        notification = Notification.objects.filter(user=self.user).last()
        assert notification.message == f'قرارداد واریز مستقیم {deposit.contract.bank.name} شما حذف شد.'

    @patch('exchange.direct_debit.api.views.random')
    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_deposit_throttled_banks(self, mock_deposit, mock_random):
        mock_deposit.return_value = MockResponse(self.sample_faraboom_response, status.HTTP_200_OK)
        Settings.set_cached_json(
            'direct_debit_throttled_banks',
            {
                self.contract.bank.bank_id: 0.1,
            },
        )
        mock_random.return_value = 0.2

        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': self.contract.id}
        response = self.client.post(url, data)

        assert response.status_code == 422
        assert response.json() == {
            'code': 'DeactivatedBankError',
            'message': 'The bank is not active',
            'status': 'failed',
        }

        mock_random.return_value = 0.01

        response = self.client.post(url, data)

        assert response.status_code != 422  # Should not get 422, anything else is ok for this test

        Settings.set_cached_json('direct_debit_throttled_banks', {})

        response = self.client.post(url, data)

        assert response.status_code != 422  # Should not get 422, anything else is ok for this test

    def test_deposit_with_deactivated_contract_with_code_2154(self):
        self.run_contract_deactivated_test_with_error(error_code='2154', error_message='این پیمان در بانک لغو شده است.')

    def test_deposit_with_deactivated_contract_with_code_2213(self):
        self.run_contract_deactivated_test_with_error(
            error_code='2213', error_message='کاربر برای پذیرنده معتبر نمی باشد.'
        )

    def test_deposit_with_deactivated_contract_with_code_2010(self):
        self.run_contract_deactivated_test_with_error(error_code='2010', error_message='وضعیت واگذاری نامعتبر است.')

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('exchange.direct_debit.models.transaction.on_commit', lambda t: t())
    @patch('exchange.direct_debit.tasks.FaraboomHandler.change_contract_status')
    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_deactivate_contract_faraboom_call_failure(self, mock_deposit_response, mock_change_status):
        mock_response = self.mock_faraboom_deposit_error(
            mock_deposit_response,
            error_code='2154',
            error_message='این پیمان در بانک لغو شده است.',
        )
        mock_change_status.side_effect = Exception("failed")

        response = self.perform_deposit_request(amount=100003)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'status': 'failed',
            'code': 'ContractCanceledInBankError',
            'message': 'This contract has been canceled in the bank.',
        }

        self.contract.refresh_from_db()
        assert mock_change_status.call_count == 1
        assert self.contract.status != self.contract.STATUS.deactive
        deposit = DirectDeposit.objects.filter(contract=self.contract, amount=100003).first()
        assert deposit
        assert deposit.status == DirectDeposit.STATUS.failed
        assert deposit.third_party_response == mock_response.json_data

    def mock_faraboom_deposit_error(self, mock_direct_deposit_response, error_code, error_message):
        mock_response = MockResponse(
            json_data={
                'code': error_code,
                'error': error_message,
                'errors': [{'code': error_code, 'error': error_message}],
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        mock_direct_deposit_response.side_effect = HTTPError('http_error_msg', response=mock_response)
        return mock_response

    def perform_deposit_request(self, amount):
        url = '/direct-debit/deposit'
        data = {'amount': amount, 'contract': self.contract.id}
        return self.client.post(url, data)


class DirectDepositCheckTimeoutDepositCronTestCase(TestCase, DirectDebitMixins):
    def setUp(self):
        self.user = User.objects.create_user(username='testalitestkafytest', password='<PASSWORD>')

    @patch('exchange.direct_debit.crons.DirectDebitUpdateDeposit')
    def test_check_timeout_deposit_cron(self, mock_update_deposit_cls):
        mock_instance = MagicMock()
        mock_update_deposit_cls.return_value = mock_instance

        timeout_deposit_1 = self.create_deposit(self.user, status=DirectDeposit.STATUS.timeout)
        timeout_deposit_2 = self.create_deposit(self.user, status=DirectDeposit.STATUS.timeout)
        timeout_deposit_3 = self.create_deposit(self.user, status=DirectDeposit.STATUS.timeout)
        timeout_deposit_3.created_at = ir_now() - datetime.timedelta(minutes=15)
        timeout_deposit_3.save()
        self.create_deposit(self.user, status=DirectDeposit.STATUS.in_progress)
        self.create_deposit(self.user, status=DirectDeposit.STATUS.failed)
        DirectDebitCheckTimeoutDepositCron().run()
        assert mock_instance.resolve_diff.call_count == 2
        self.assertCountEqual(
            mock_update_deposit_cls.call_args_list,
            [call(trace_id=timeout_deposit_1.trace_id), call(trace_id=timeout_deposit_2.trace_id)],
        )


class DirectDepositTransactionTestCase(TransactionTestFastFlushMixin, TransactionTestCase, DirectDebitMixins):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='DirectDepositTransactionTestCase@nobitex.com',
            email='DirectDepositTransactionTestCase@nobitex.com',
            first_name='mostafa',
            last_name='heidarian',
        )
        self.user.user_type = User.USER_TYPE_LEVEL1
        vp = self.user.get_verification_profile()
        vp.mobile_confirmed = True
        vp.mobile_identity_confirmed = True
        vp.email_confirmed = True
        vp.save()
        self.user.auth_token = Token.objects.create(user=self.user, key='124536755')
        self.user.mobile = '09151234567'
        self.user.save()

        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'
        self.request_feature(self.user, 'done')
        self.contract = self.create_contract(user=self.user)
        self.contract.trace_id = 'cdklcdke-b7jk-5hg-997c-b991acdac3b6'
        self.contract.contract_id = 'kr7JBZLrkMNZ'
        self.contract.save()

    @patch('exchange.direct_debit.models.FaraboomHandler.direct_deposit')
    def test_third_party_unexpended_error(self, response_mock):
        response_mock.side_effect = ValueError()
        url = '/direct-debit/deposit'
        data = {'amount': 100000, 'contract': self.contract.id}

        assert not DirectDeposit.objects.filter(contract=self.contract, amount=100000)

        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json() == {
            'code': 'ThirdPartyClientError',
            'message': 'An error occurred when trying to connect to third-party API',
            'status': 'failed',
        }
        notification = Notification.objects.filter(user=self.user).last()
        assert notification.message == f'واریز مستقیم {self.contract.bank.name} شما انجام نشد.'

        deposit = DirectDeposit.objects.filter(contract=self.contract, amount=100000)
        assert deposit
