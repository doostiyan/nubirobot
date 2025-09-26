from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.wallet.models import Wallet


class TransactionsApiTest(APITestCase):
    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        cls.spot_wallet = Wallet.get_user_wallet(cls.user, Currencies.rls)
        for i, amount in enumerate([1_000_000_0, 1_400_000_0, -2_000_000_0, 1_800_000_0, 5_500_000_0, -4_300_000_0]):
            cls.spot_wallet.create_transaction('manual', amount).commit()
            cls.spot_wallet.refresh_from_db()

        Wallet.get_user_wallet(cls.user, Currencies.usdt).create_transaction('manual', '113.76').commit()

        cls.margin_wallet = Wallet.get_user_wallet(cls.user, Currencies.rls, tp=Wallet.WALLET_TYPE.margin)
        for i, amount in enumerate([2_000_000_0, -55_000_0, -145_000_0, -1_800_000_0]):
            cls.margin_wallet.create_transaction('manual', amount).commit()
            cls.margin_wallet.refresh_from_db()

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def _test_successful_wallet_transaction_list(self, wallet):
        data = self.client.get('/users/wallets/transactions/list', {'wallet': wallet.id}).json()
        assert data
        assert data['status'] == 'ok'
        assert 'transactions' in data
        return data['transactions']

    def test_successful_wallet_transaction_list_spot_wallet(self):
        transactions = self._test_successful_wallet_transaction_list(self.spot_wallet)
        assert transactions
        assert len(transactions) == 6
        assert transactions[0]['amount'] == '-43000000'
        assert transactions[5]['amount'] == '10000000'

    def test_successful_wallet_transaction_list_margin_wallet(self):
        transactions = self._test_successful_wallet_transaction_list(self.margin_wallet)
        assert transactions
        assert len(transactions) == 4
        assert transactions[0]['amount'] == '-18000000'
        assert transactions[3]['amount'] == '20000000'

    def test_unsuccessful_wallet_transaction_list_invalid_wallet_id(self):
        for wallet_id in ('abc', 'None', 1.23):
            data = self.client.get('/users/wallets/transactions/list', {'wallet': wallet_id}).json()
            assert data['status'] == 'failed'
            assert data['message'] == f'Invalid integer value: "{wallet_id}"'
            assert data['code'] == 'ParseError'

        data = self.client.get('/users/wallets/transactions/list').json()
        assert data['status'] == 'failed'
        assert data['message'] == 'Missing integer value'
        assert data['code'] == 'ParseError'
