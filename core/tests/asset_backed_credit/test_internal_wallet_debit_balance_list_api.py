from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.internal.services import Services
from exchange.base.models import Currencies
from exchange.wallet.models import Wallet as ExchangeWallet
from tests.helpers import create_internal_token, mock_internal_service_settings


class DebitWalletBalanceListApiTestCase(APITestCase):
    URL = '/internal/asset-backed-credit/wallets/debit/balances'

    @classmethod
    def setUpTestData(cls) -> None:
        user = User.objects.get(pk=201)
        cls.user = user
        cls.charge_debit_wallet(user, Currencies.usdt, Decimal('100'))
        cls.charge_debit_wallet(user, Currencies.btc, Decimal('1'))

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token(Services.CORE.value)}')

    @mock_internal_service_settings
    def test_get_wallet_balances(self):
        url = f'{self.URL}?user_id={self.user.uid}'
        resp = self.client.get(path=url, content_type='application/json')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == {'status': 'ok', 'wallets': {'13': '100', '10': '1'}}

    @mock_internal_service_settings
    def test_get_wallet_balances_failed_no_user_id(self):
        resp = self.client.get(path=self.URL, content_type='application/json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json() == {'status': 'failed', 'message': 'missing user_id.'}

    @staticmethod
    def charge_debit_wallet(user, currency, amount):
        wallet = ExchangeWallet.get_user_wallet(user, currency, tp=ExchangeWallet.WALLET_TYPE.debit)
        wallet.create_transaction(tp='manual', amount=amount).commit()
        wallet.refresh_from_db()
        return wallet
