import datetime
from datetime import timedelta
from unittest.mock import patch

from django.utils.timezone import now
from pytz import utc
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.system.models import BotTransaction
from exchange.wallet.models import Wallet, Transaction


class BotTransactionsApiTest(APITestCase):

    def setUp(self) -> None:
        self.amounts = [100_0, 200_0, 300_0]
        self.utc_now = datetime.datetime.now(tz=utc)
        self.now = now()
        self.created_ats = [self.now - datetime.timedelta(days=3),
                            self.now - datetime.timedelta(days=2),
                            self.now - datetime.timedelta(days=1)]
        self.url = reverse('bot_transactions_list_get')

        self.user = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        Wallet.create_user_wallets(self.user)
        Wallet.create_user_wallets(self.user2)
        self.usdt_wallet = Wallet.objects.get(user=self.user, currency=Currencies.usdt, type=Wallet.WALLET_TYPE.spot)

        transactions_info = [{
            'tp': Transaction.TYPE.deposit,
            'ref_module': Transaction.REF_MODULES['BankDeposit'],
            'amount': self.amounts[i // 2] / 2,
            'created_at': self.created_ats[i // 2],
            'wallet': self.usdt_wallet,
        } for i in range(len(self.amounts) * 2)]
        self.transactions = Transaction.objects.bulk_create(
            [Transaction(**transactions_info[i]) for i in range(len(transactions_info))]
        )
        self.bot_transactions = [BotTransaction.objects.create(
            id=i + 1,
            wallet=self.usdt_wallet,
            amount=self.amounts[i],
            balance=self.amounts[i],
            created_at=self.created_ats[i],
            description='',
        ) for i in range(3)]
        for i in range(3):
            self.bot_transactions[i].transactions.add(self.transactions[2 * i])
            self.bot_transactions[i].transactions.add(self.transactions[2 * i + 1])
            self.bot_transactions[i].created_at = self.created_ats[i]
            self.bot_transactions[i].save()
        self.user2_usdt_wallet = Wallet.objects.get(
            user=self.user2, currency=Currencies.usdt, type=Wallet.WALLET_TYPE.spot
        )

        transactions_info = [{
            'tp': Transaction.TYPE.deposit,
            'ref_module': Transaction.REF_MODULES['BankDeposit'],
            'amount': self.amounts[i // 2] / 2,
            'created_at': self.created_ats[i // 2],
            'wallet': self.user2_usdt_wallet,
        } for i in range(len(self.amounts) * 2)]
        self.transactions = Transaction.objects.bulk_create(
            [Transaction(**transactions_info[i]) for i in range(len(transactions_info))]
        )
        self.bot_transactions = [
            BotTransaction.objects.create(
                id=100 + i + 1,
                wallet=self.user2_usdt_wallet,
                amount=self.amounts[i],
                balance=self.amounts[i],
                created_at=self.created_ats[i],
                description='',
            )
            for i in range(3)
        ]
        for i in range(3):
            self.bot_transactions[i].transactions.add(self.transactions[2 * i])
            self.bot_transactions[i].transactions.add(self.transactions[2 * i + 1])
            self.bot_transactions[i].created_at = self.created_ats[i]
            self.bot_transactions[i].save()

    def tearDown(self):
        Transaction.objects.all().delete()
        BotTransaction.objects.all().delete()

    @patch('exchange.system.views.is_feature_enabled', return_value=True)
    @patch('exchange.system.views.is_internal_ip', return_value=True)
    def test_get_all_bot_transactions_successfully(self, mock_is_internal_ip, mock_feature_flag):
        right_now = now()
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        transactions_list = response.json().get('data').get('transactions')
        assert len(transactions_list) == 2
        transactions_list.sort(key=lambda x: x['id'])
        transactions = list(
            Transaction.objects.filter(wallet__user=self.user, created_at__gte=right_now - timedelta(days=2)).order_by(
                'id'
            )
        )
        transactions.sort(key=lambda x: x.id)
        assert len(transactions) == 2
        assert transactions_list == [{'id': transactions[0].id, 'amount': '1500', 'currency': 'usdt', 'description': '',
                                      'created_at': transactions[0].created_at.isoformat(), 'balance': None},
                                     {'id': transactions[1].id, 'amount': '1500', 'currency': 'usdt', 'description': '',
                                      'created_at': transactions[1].created_at.isoformat(), 'balance': None}]

    @patch('exchange.system.views.is_feature_enabled', return_value=True)
    @patch('exchange.system.views.is_internal_ip', return_value=True)
    def test_get_bot_transactions_after_an_id(self, mock_is_internal_ip, mock_feature_flag):
        response = self.client.get(self.url, data={'transactionId': '2'})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json().get('data').get('transactions')) == 6

    @patch('exchange.system.views.is_feature_enabled', return_value=True)
    @patch('exchange.system.views.is_internal_ip', return_value=True)
    def test_get_bot_transactions_after_a_date(self, mock_is_internal_ip, mock_feature_flag):
        ts = (self.utc_now - datetime.timedelta(days=1, hours=1)).timestamp()
        response = self.client.get(self.url, data={'since': str(ts)})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json().get('data').get('transactions')) == 2

    @patch('exchange.system.views.is_feature_enabled', return_value=True)
    @patch('exchange.system.views.is_internal_ip', return_value=True)
    def test_get_bot_transactions_after_a_date_and_id(self, mock_is_internal_ip, mock_feature_flag):
        ts = (self.utc_now - datetime.timedelta(days=1, hours=1)).timestamp()
        response = self.client.get(self.url, data={'since': ts, 'transactionId': '2'})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json().get('data').get('transactions')) == 2

    @patch('exchange.system.views.is_feature_enabled', return_value=True)
    @patch('exchange.system.views.is_internal_ip', return_value=False)
    def test_external_ip_access_denied(self, mock_is_internal_ip, mock_feature_flag):
        ts = (self.utc_now - datetime.timedelta(days=1, hours=1)).timestamp()
        response = self.client.get(self.url, data={'since': ts, 'transactionId': '2'})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json().get('code') == 'AccessDenied'

    @patch('exchange.system.views.is_feature_enabled', return_value=False)
    @patch('exchange.system.views.is_internal_ip', return_value=True)
    def test_feature_flag_disabled_access_denied(self, mock_is_internal_ip, mock_feature_flag):
        ts = (self.utc_now - datetime.timedelta(days=1, hours=1)).timestamp()
        response = self.client.get(self.url, data={'since': ts, 'transactionId': '2'})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json().get('code') == 'AccessDenied'
