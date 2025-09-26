from decimal import Decimal
from typing import List
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User, UserEvent
from exchange.base.models import Currencies, Settings
from exchange.wallet.constants import TRANSACTION_MAX
from exchange.wallet.models import Transaction, Wallet


@patch('exchange.accounts.models.settings.IS_TESTNET', True)
class CreateBulkTransactionsAPITest(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.get(id=201)
        self._add_to_test_accounts(self.admin_user.username)
        self.normal_user = User.objects.get(id=202)
        self.test_user1 = User.objects.create_user(username='test1', email='test1@test.com', password='testpass123')
        self.test_user2 = User.objects.create_user(username='test2', email='test2@test.com', password='testpass123')
        self.user_without_wallet = User.objects.create_user(
            username='test3', email='test3@test.com', password='testpass123'
        )

        # Create wallets for test users
        self.initial_balance = Decimal('100')
        self.wallet1 = Wallet.objects.create(
            user=self.test_user1,
            currency=Currencies.btc,
            type=Wallet.WALLET_TYPE.margin,
            balance=self.initial_balance,
        )
        self.wallet2 = Wallet.objects.create(
            user=self.test_user2, currency=Currencies.btc, type=Wallet.WALLET_TYPE.margin
        )

        self.url = '/QA/wallets/charge'

    def _add_to_test_accounts(self, username: str):
        test_accounts: List['str'] = Settings.get_list('username_test_accounts')
        if username not in test_accounts:
            test_accounts.append(username)
            Settings.set_dict('username_test_accounts', test_accounts)

    def test_permission_denied_for_normal_user(self):
        """Test that normal users cannot access the API"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.normal_user.auth_token.key}')
        response = self.client.post(
            self.url, {'user_ids': f'{self.test_user1.id},{self.test_user2.id}', 'currency': 'btc', 'amount': '1.0'}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()['code'] == 'PermissionDenied'

    def test_missing_user_ids(self):
        """Test validation for missing user_ids"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_user.auth_token.key}')
        response = self.client.post(self.url, {'currency': 'btc', 'amount': '1.0'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['code'] == 'UserIdInvalid'

    def test_invalid_currency(self):
        """Test validation for invalid currency"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_user.auth_token.key}')
        response = self.client.post(
            self.url,
            {'user_ids': f'{self.test_user1.id},{self.test_user2.id}', 'currency': 'invalid_currency', 'amount': '1.0'},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['code'] == 'CurrencyInvalid'

    def test_invalid_amount(self):
        """Test validation for invalid amount"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_user.auth_token.key}')
        response = self.client.post(
            self.url,
            {'user_ids': f'{self.test_user1.id},{self.test_user2.id}', 'currency': 'btc', 'amount': 'invalid_amount'},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['code'] == 'AmountInvalid'

    def test_successful_bulk_transaction(self):
        """Test successful bulk transaction creation"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_user.auth_token.key}')
        amount = '1.5'

        response = self.client.post(
            self.url,
            {
                'user_ids': f'{self.test_user1.id},{self.test_user2.id},{self.user_without_wallet.id}',
                'currency': 'btc',
                'amount': amount,
                'type': 'margin',
                'create': True,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert 'currency' in data
        assert data['currency'] == 'btc'
        assert 'wallets' in data
        assert len(data['wallets']) == 3

        # Verify wallet balances were updated
        self.wallet1.refresh_from_db()
        self.wallet2.refresh_from_db()
        assert self.wallet1.balance == self.initial_balance + Decimal(amount)
        assert self.wallet2.balance == Decimal(amount)
        created_wallet = Wallet.objects.filter(user=self.user_without_wallet, type=Wallet.WALLET_TYPE.margin)
        assert created_wallet.exists()
        created_wallet = created_wallet.first()
        assert created_wallet.balance == Decimal(amount)

        # Verify transactions were created
        for wallet in [self.wallet1, self.wallet2, created_wallet]:
            assert Transaction.objects.filter(wallet=wallet, amount=Decimal(amount)).exists()

        # Verify UserEvent was created
        assert UserEvent.objects.filter(
            user=self.admin_user, action=UserEvent.ACTION_CHOICES.add_manual_transaction
        ).exists()

    def test_mixed_valid_invalid_users(self):
        """Test handling of mix of valid and invalid user IDs"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_user.auth_token.key}')
        invalid_user_id = 99999
        amount = '1.0'

        response = self.client.post(
            self.url,
            {
                'user_ids': f'{self.test_user1.id},{invalid_user_id}',
                'currency': 'btc',
                'amount': amount,
                'type': 'margin',
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response contains both valid and invalid users
        assert len(data['wallets']) == 2

        # Verify valid user's wallet was updated
        self.wallet1.refresh_from_db()
        assert self.wallet1.balance == self.initial_balance + Decimal(amount)

        # Verify invalid user is in response with null values
        invalid_user_response = next((w for w in data['wallets'] if w['user_id'] == invalid_user_id), None)
        assert invalid_user_response
        assert invalid_user_response['wallet_id'] is None
        assert invalid_user_response['balance'] is None

    def test_large_amount_transaction(self):
        """Test handling of large amounts that exceed TRANSACTION_MAX"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_user.auth_token.key}')
        large_amount = str(TRANSACTION_MAX + 1)

        response = self.client.post(
            self.url, {'user_ids': f'{self.test_user1.id}', 'currency': 'btc', 'amount': large_amount, 'type': 'margin'}
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify multiple transactions were created for the large amount
        transactions = Transaction.objects.filter(wallet=self.wallet1)
        assert transactions.count() == 2

        # Verify total amount matches
        total_amount = sum(t.amount for t in transactions)
        assert total_amount == Decimal(large_amount)
