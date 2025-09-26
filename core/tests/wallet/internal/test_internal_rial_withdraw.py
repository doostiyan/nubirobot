import datetime
import json
from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from rest_framework import status

from exchange.accounts.models import BankAccount, User, UserRestriction
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.internal.services import Services
from exchange.base.models import RIAL, Settings
from exchange.wallet.models import Wallet, WithdrawRequest, WithdrawRequestPermit
from tests.helpers import APITestCaseWithIdempotency, create_internal_token, mock_internal_service_settings

info = deepcopy(CURRENCY_INFO)
info[2]['network_list']['FIAT_MONEY']['withdraw_enable'] = False


class InternalRialWithdrawTest(APITestCaseWithIdempotency):
    URL = '/internal/wallets/withdraw-rial'

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token(Services.ABC.value)}')
        self.user = User.objects.get(pk=201)
        self.user.user_type = User.USER_TYPES.level2
        self.user.mobile = '09022551452'
        self.user.save()
        self.profile = self.user.get_verification_profile()
        self.profile.mobile_confirmed = True
        self.profile.save()
        self.abc_user = User.objects.get(pk=202)
        self.wallet = Wallet.get_user_wallet(self.user, RIAL)
        self.wallet.balance = Decimal('10_000_000')
        self.wallet.save()
        self.bank_account = BankAccount.objects.create(
            user=self.user, account_number='25636514125648', shaba_number='IR299980000000002030098504', confirmed=True
        )
        Settings.set('withdraw_id', json.dumps({'jibit_withdraw_enabled': True}))
        Settings.set('vandar_max_withdrawal', Decimal('100_000_000'))

    @mock_internal_service_settings
    @patch('exchange.accounts.models.BankAccount.get_system_gift_account')
    def test_withdraw_successfully(self, mock_get_system_gift_account):
        mock_get_system_gift_account.return_value = []
        data = {
            'userId': self.user.uid,
            'amount': 150000,
            'shabaNumber': self.bank_account.shaba_number,
            'explanation': 'تسویه نهایی با سرویس دهنده',
        }
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_200_OK
        withdraw_request = WithdrawRequest.objects.filter(
            wallet=Wallet.get_user_wallet(self.user, RIAL),
            target_address='جیبیت: IR299980000000002030098504',
            target_account=self.bank_account,
            amount=Decimal(150000),
            network='FIAT_MONEY',
            requester_service=Services.ABC.value,
            explanations='تسویه نهایی با سرویس دهنده',
            tag=None,
            fee=150000 // 100,
            invoice=None,
            contract_address=None,
        )
        assert withdraw_request.exists()
        assert response.json() == {'id': withdraw_request.first().id}

    @mock_internal_service_settings
    def test_withdraw_by_limited_user(self):
        # test with withdrawRequest limitation
        UserRestriction.add_restriction(self.user, 'WithdrawRequest')
        data = {
            'userId': self.user.uid,
            'amount': 150000,
            'shabaNumber': self.bank_account.shaba_number,
        }
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {'code': 'WithdrawUnavailable', 'message': 'WithdrawUnavailable', 'status': 'failed'}

        # test with WithdrawRequestRial limitation
        UserRestriction.add_restriction(self.user, 'WithdrawRequestRial')
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {'code': 'WithdrawUnavailable', 'message': 'WithdrawUnavailable', 'status': 'failed'}

        # test negative balance of user wallet
        self.wallet.balance = -Decimal('1000')
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {'code': 'WithdrawUnavailable', 'message': 'WithdrawUnavailable', 'status': 'failed'}

        # test if user has WithdrawRequestPermit and one limitation
        WithdrawRequestPermit.objects.create(
            user=self.user,
            currency=self.wallet.currency,
            amount_limit=Decimal('150000'),
            effective_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
        )
        UserRestriction.add_restriction(self.user, 'WithdrawRequestRial')
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_200_OK

    @mock_internal_service_settings
    def test_target_address_does_not_exist(self):
        data = {
            'userId': self.user.uid,
            'amount': 150000,
            'shabaNumber': '1234567899',
        }
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {'error': 'NotFound', 'message': 'No BankAccount matches the given query.'}

    @mock_internal_service_settings
    def test_jibit_is_disabled(self):
        data = {
            'userId': self.user.uid,
            'amount': 150000,
            'shabaNumber': self.bank_account.shaba_number,
        }

        Settings.set('withdraw_id', json.dumps({'jibit_withdraw_enabled': False}))
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'JibitPaymentIdDisabled',
            'message': 'jibit withdraw is disabled.',
            'status': 'failed',
        }

    @mock_internal_service_settings
    def test_vandar_is_disabled(self):
        self.bank_account.shaba_number = 'IR299990000000002030098504'  # vandar shaba sample
        self.bank_account.save()
        data = {
            'userId': self.user.uid,
            'amount': 150000,
            'shabaNumber': self.bank_account.shaba_number,
        }

        Settings.set('withdraw_id', json.dumps({'vandar_withdraw_enabled': False}))
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'VandarPaymentIdDisabled',
            'message': 'Vandar withdraw is disabled.',
            'status': 'failed',
        }

    @mock_internal_service_settings
    def test_insufficient_balance(self):
        data = {
            'userId': self.user.uid,
            'amount': 150000,
            'shabaNumber': self.bank_account.shaba_number,
        }
        self.wallet.balance = Decimal('1000')
        self.wallet.save()
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'InsufficientBalance',
            'message': 'Insufficient Balance.',
            'status': 'failed',
        }

    @mock_internal_service_settings
    def test_call_service_by_normal_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        data = {
            'userId': self.user.uid,
            'amount': 150000,
            'shabaNumber': self.bank_account.shaba_number,
        }
        response = self.client.post(self.URL, data=data)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @mock_internal_service_settings
    def test_daily_shaba_withdraw_limit_exceeded(self):
        self.wallet.balance = Decimal('1_000_000_000_0')
        self.wallet.save()
        withdraw_request = WithdrawRequest.objects.create(
            tp=WithdrawRequest.TYPE.normal,
            wallet=self.wallet,
            target_address=self.bank_account.shaba_number,
            target_account=self.bank_account,
            amount=Decimal('500_000_000_0'),
        )
        withdraw_request.do_verify()
        data = {
            'userId': self.user.uid,
            'amount': 150000,
            'shabaNumber': self.bank_account.shaba_number,
        }
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'ShabaWithdrawCannotProceed',
            'message': 'Shaba withdraw cannot proceed. Daily Shaba withdraw limit Exceeded.',
            'status': 'failed',
        }

    @mock_internal_service_settings
    @patch("exchange.wallet.models.WithdrawRequest.check_user_limit", return_value=False)
    def test_check_user_limit(self, mock_check_user_limit):
        data = {
            'userId': self.user.uid,
            'amount': 150000,
            'shabaNumber': self.bank_account.shaba_number,
        }
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'WithdrawLimitReached',
            'message': 'msgWithdrawLimitReached',
            'status': 'failed',
        }

    @mock_internal_service_settings
    @patch('exchange.accounts.userlevels.UserLevelManager.is_eligible_to_withdraw', return_value=False)
    def test_is_eligible_to_withdraw(self, mock_eligible_to_withdraw):
        data = {
            'userId': self.user.uid,
            'amount': 150000,
            'shabaNumber': self.bank_account.shaba_number,
        }
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'WithdrawAmountLimitation',
            'message': 'WithdrawAmountLimitation',
            'status': 'failed',
        }

    @mock_internal_service_settings
    @patch('exchange.accounts.userlevels.UserLevelManager.is_eligible_to_vandar_withdraw', return_value=False)
    def test_is_eligible_to_vandar_withdraw(self, mock_eligible_to_withdraw):
        self.bank_account.shaba_number = 'IR299990000000002030098504'  # vandar shaba sample
        self.bank_account.save()
        data = {
            'userId': self.user.uid,
            'amount': 150000,
            'shabaNumber': self.bank_account.shaba_number,
        }
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'VandarPaymentIdDisabled',
            'message': 'Vandar withdraw is disabled.',
            'status': 'failed',
        }

    @mock_internal_service_settings
    def test_user_with_other_user_shaba_number(self):
        new_user = User.objects.get(pk=202)
        bank_account = BankAccount.objects.create(
            user=new_user, account_number='25636514125648', shaba_number='IR299980000000002520098504', confirmed=True
        )

        data = {
            'userId': self.user.uid,
            'amount': 150000,
            'shabaNumber': bank_account.shaba_number,
        }

        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {'error': 'NotFound', 'message': 'No BankAccount matches the given query.'}

    @mock_internal_service_settings
    def test_withdraw_request_with_unconfirmed_bank_account(self):
        new_user = User.objects.get(pk=202)
        bank_account = BankAccount.objects.create(
            user=new_user, account_number='25636514125648', shaba_number='IR299980000000002520098504', confirmed=False
        )
        data = {
            'userId': new_user.uid,
            'amount': 150000,
            'shabaNumber': bank_account.shaba_number,
        }
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {'error': 'NotFound', 'message': 'No BankAccount matches the given query.'}

    @mock_internal_service_settings
    @patch('exchange.wallet.models.WithdrawRequest.can_withdraw_shaba', return_value=True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_eligible_to_vandar_withdraw', return_value=True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_eligible_to_withdraw', return_value=True)
    def test_max_amount_when_provider_is_vandar(
        self, mock_eligible_to_withdraw, mock_eligible_to_vandar, mock_can_withdraw_shaba
    ):
        self.bank_account.shaba_number = 'IR299990000000002030098504'  # vandar shaba sample
        self.wallet.balance = Decimal('600_000_000_0')
        self.wallet.save()
        self.bank_account.save()
        data = {
            'userId': self.user.uid,
            'amount': 500_000_000_1,
            'shabaNumber': self.bank_account.shaba_number,
        }
        Settings.get_decimal('vandar_max_withdrawal', Decimal('500_000_000_0'))
        Settings.set('withdraw_id', json.dumps({'vandar_withdraw_enabled': True}))
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'AmountTooHigh',
            'message': 'Amount too high',
            'status': 'failed',
        }

    @mock_internal_service_settings
    def test_min_withdraw_amount(self):

        data = {
            'userId': self.user.uid,
            'amount': 14_900_0,
            'shabaNumber': self.bank_account.shaba_number,
        }
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'AmountTooLow',
            'message': 'Amount too low',
            'status': 'failed',
        }

    @mock_internal_service_settings
    def test_check_user_profile(self):
        data = {
            'userId': self.user.uid,
            'amount': 16_000_0,
            'shabaNumber': self.bank_account.shaba_number,
        }
        self.profile.mobile_confirmed = False
        self.profile.save()
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'code': 'InvalidMobileNumber',
            'message': 'Verified mobile number is required for withdraw.',
            'status': 'failed',
        }

    @mock_internal_service_settings
    @patch('exchange.wallet.internal.withdraw_validations.CURRENCY_INFO', info)
    def test_do_withdraw_when_is_disable(self):

        data = {
            'userId': self.user.uid,
            'amount': 16_000_0,
            'shabaNumber': self.bank_account.shaba_number,
        }

        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'code': 'WithdrawCurrencyUnavailable',
            'message': 'WithdrawCurrencyUnavailable',
            'status': 'failed',
        }

    @mock_internal_service_settings
    def test_do_withdraw_when_is_temporary_disable(self):
        data = {
            'userId': self.user.uid,
            'amount': 16_000_0,
            'shabaNumber': self.bank_account.shaba_number,
        }
        Settings.set('withdraw_enabled_rls_fiat_money', 'no')
        response = self.client.post(self.URL, data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'code': 'WithdrawDisabled',
            'message': 'Withdrawals for rls is temporary disabled.',
            'status': 'failed',
        }
