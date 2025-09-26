from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from exchange.accounts.models import BankCard, User, VerificationProfile
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings
from exchange.wallet.models import Transaction, Wallet


class TestSendDepositAndWithdrawEvents(APITestCase):
    def setUp(self):
        self.webengage_cid = uuid4()
        self.user = User.objects.create(
            username='test_user',
            email='test_user@gmail.com',
            first_name='first_name',
            birthday=datetime(year=1993, month=11, day=15),
            gender=User.GENDER.female,
            city='Tehran',
            requires_2fa=True,
            webengage_cuid=self.webengage_cid,
            mobile='09980000000',
            user_type=User.USER_TYPE_LEVEL1,
        )
        VerificationProfile.objects.update_or_create(
            user=self.user, defaults={'mobile_confirmed': True, 'email_confirmed': True}
        )
        Token.objects.create(user=self.user)
        self.url = '/users/wallets/deposit/shetab'
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.card = BankCard.objects.create(
            user=self.user,
            card_number=str(1234123412341234),
            owner_name=self.user.get_full_name(),
            bank_id=10,
            confirmed=True,
            status=BankCard.STATUS.confirmed,
        )

    @patch('exchange.web_engage.externals.web_engage.is_web_engage_active', return_value=True)
    @patch('exchange.web_engage.events.base.is_webengage_user', return_value=True)
    @patch('exchange.web_engage.events.base.task_send_event_data_to_web_engage.delay')
    def test_available_gateway_doesnt_send_webengage_event(
        self, task_send_event_data_to_web_engage: MagicMock, mock2, mock3
    ):
        resp = self.client.post(self.url, dict(amount=1000, selectedCard=self.card.id))
        assert resp.status_code == 200
        assert not task_send_event_data_to_web_engage.called

    @override_settings(IS_PROD=True)
    @patch('exchange.web_engage.externals.web_engage.is_web_engage_active', return_value=True)
    @patch('exchange.web_engage.events.base.timezone.now')
    @patch('exchange.web_engage.events.base.is_webengage_user', return_value=True)
    @patch('exchange.web_engage.events.base.task_send_event_data_to_web_engage.delay')
    def test_unavailable_gateway_sends_webengage_event(
        self, task_send_event_data_to_web_engage: MagicMock, mock2, now_mock, mock3
    ):
        test_now = datetime(year=1992, month=2, day=5)
        now_mock.return_value = test_now
        Settings.set('shetab_deposit_backend', 'fake_gateway')
        resp = self.client.post(self.url, dict(amount=1000, selectedCard=self.card.id))
        assert resp.json() == {
            'status': 'failed',
            'code': 'InvalidGateway',
            'message': 'ShetabDespoitUnavailable',
        }
        task_send_event_data_to_web_engage.assert_called_once_with(
            data={
                'eventName': 'shetab_gateway_unavailable',
                'eventTime': test_now.strftime('%Y-%m-%dT%H:%M:%S%z'),
                'eventData': {},
                'userId': self.user.get_webengage_id(),
            }
        )

    @override_settings(IS_PROD=True)
    @patch('exchange.web_engage.externals.web_engage.is_web_engage_active', return_value=True)
    @patch('exchange.web_engage.events.base.timezone.now')
    @patch('exchange.web_engage.events.base.is_webengage_user', return_value=True)
    @patch('exchange.web_engage.events.base.task_send_event_data_to_web_engage.delay')
    def test_send_deposit_event(self, task_send_event_data_to_web_engage: MagicMock, mock2, now_mock, mock3):
        test_now = datetime(year=1992, month=2, day=5)
        now_mock.return_value = test_now
        rial_wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        Transaction.objects.create(
            wallet=rial_wallet,
            tp=Transaction.TYPE.deposit,
            amount=10,
            created_at=ir_now(),
            ref_module=Transaction.REF_MODULES['ConfirmedWalletDeposit'],
        )
        task_send_event_data_to_web_engage.assert_called_once_with(
            data={
                'eventName': 'deposit',
                'eventTime': test_now.strftime('%Y-%m-%dT%H:%M:%S%z'),
                'eventData': {
                    'currency': 2,
                    'user_level_code': self.user.user_type,
                    'amount_code': 1,
                    'type': 'Other',
                },
                'userId': self.user.get_webengage_id(),
            }
        )

        task_send_event_data_to_web_engage.reset_mock()
        Transaction.objects.create(
            wallet=rial_wallet,
            tp=Transaction.TYPE.deposit,
            amount=1000000,
            created_at=ir_now(),
            ref_module=Transaction.REF_MODULES['ShetabDeposit'],
        )
        task_send_event_data_to_web_engage.assert_called_once_with(
            data={
                'eventName': 'deposit',
                'eventTime': test_now.strftime('%Y-%m-%dT%H:%M:%S%z'),
                'eventData': {
                    'currency': 2,
                    'user_level_code': self.user.user_type,
                    'amount_code': 4,
                    'type': 'ShetabDeposit',
                },
                'userId': self.user.get_webengage_id(),
            }
        )

        task_send_event_data_to_web_engage.reset_mock()
        Transaction.objects.create(
            wallet=rial_wallet,
            tp=Transaction.TYPE.deposit,
            amount=22000000,
            created_at=ir_now(),
            ref_module=Transaction.REF_MODULES['DirectDebitUserTransaction'],
        )
        task_send_event_data_to_web_engage.assert_called_once_with(
            data={
                'eventName': 'deposit',
                'eventTime': test_now.strftime('%Y-%m-%dT%H:%M:%S%z'),
                'eventData': {
                    'currency': 2,
                    'user_level_code': self.user.user_type,
                    'amount_code': 6,
                    'type': 'DirectDebitUserTransaction',
                },
                'userId': self.user.get_webengage_id(),
            }
        )

        task_send_event_data_to_web_engage.reset_mock()
        Transaction.objects.create(
            wallet=rial_wallet,
            tp=Transaction.TYPE.deposit,
            amount=500000000,
            created_at=ir_now(),
            ref_module=Transaction.REF_MODULES['BankDeposit'],
        )
        task_send_event_data_to_web_engage.assert_called_once_with(
            data={
                'eventName': 'deposit',
                'eventTime': test_now.strftime('%Y-%m-%dT%H:%M:%S%z'),
                'eventData': {
                    'currency': 2,
                    'user_level_code': self.user.user_type,
                    'amount_code': 11,
                    'type': 'BankDeposit',
                },
                'userId': self.user.get_webengage_id(),
            }
        )
